#include <arpa/inet.h>
#include <algorithm>
#include <condition_variable>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>
// Needs C++17
#include <filesystem>

#include "cxxopts.hpp"
#include "zstr.hpp"
#include <zim/zim.h>
#include <zim/file.h>
#include <zim/fileiterator.h>

namespace fs = std::filesystem;

/** Holds disambiguation patterns in titles for languages we support. */
std::map<std::string, std::string> disambig = {
    {"hu", "(egyértelműsítő lap)"}, {"en", "(disambiguation)"}
};

/** Keeps Options alive so that the returned ParseResult is valid. */
class ArgumentParser {
public:
    ArgumentParser(char* argv[]) {
        try {
            options = std::unique_ptr<cxxopts::Options>(new cxxopts::Options(
                argv[0], "Converts a static Wikipedia HTML dump in a .zim file "
                         "to a directory of files. Each file contains a list "
                         "of uint32_t-string tuples, the first being the "
                         "number of characters in the latter."
            ));
            options
                ->add_options()
                ("i,input-file", "the name of the source .zim file",
                 cxxopts::value<std::string>())
                ("o,output-dir", "the name of the output directory",
                 cxxopts::value<std::string>())
                ("l,language", "the two-letter language code of the Wikipedia dump",
                 cxxopts::value<std::string>()->default_value("hu"))
                ("d,documents", "the number of articles saved into a "
                                "single output file",
                 cxxopts::value<size_t>()->default_value("2500"))
                ("Z,zeroes", "the number of zeroes in the output files' names.",
                 cxxopts::value<size_t>()->default_value("4"))
                ("T,threads", "the number of parallel threads to use.",
                 cxxopts::value<size_t>()->default_value("10"))
                ("h,help", "print help")
            ;
        } catch (const cxxopts::OptionException& e) {
            std::cerr << "Error parsing options: " << e.what() << std::endl;
            exit(1);
        }
    }

    cxxopts::ParseResult parse(int argc, char* argv[]) {
        try { 
            auto args = options->parse(argc, argv);
            if (args.count("help")) {
                std::cout << options->help({""}) << std::endl;
                exit(0);
            }
            if (!args.count("input-file") || !args.count("output-dir")) {
                std::cout << "Both -i and -o must be specified." << std::endl;
                exit(1);
            }
            std::string language = args["language"].as<std::string>();
            std::vector<std::string> v = {"aha", "baha"};
            if (!disambig.count(language)) {
                std::cout << "Language '" << language << "' is no supported. "
                          << "Choose between 'en' and 'hu'." << std::endl;
            }
            return args;
        } catch (const cxxopts::OptionException& e) {
            std::cerr << "Error parsing options: " << e.what() << std::endl;
            exit(1);
        }
    }

private:
    std::unique_ptr<cxxopts::Options> options;
};


/**
 * List the indices of valid WP articles.
 *
 * \warning
 * In the latest version of the library, this should be
 * \c zim::article_index_type instead. The version in the Ubuntu repository,
 * however, is older, and uses \c zim::size_type. This might cause problems if
 * the version is updated.
 */
typedef std::vector<zim::size_type> IndexList;
/**
 * The name (number) of the file and the titles of the articles it should
 * contain.
 */
typedef std::pair<size_t, IndexList> FileData;


struct ZimData {
    ZimData(size_t num_threads) : max_size(num_threads), curr_size(0),
                                  filter_done(false) {
    }

    void push_job(FileData file_data) {
        {
            std::cerr << "Waiting on queue_not_full..." << std::endl;
            std::unique_lock<std::mutex> lock(mutex);
            queue_not_full.wait(lock, [this]{return curr_size < max_size;});
        }
        {
            std::cerr << "Pushing job..." << std::endl;
            std::lock_guard<std::mutex> guard(mutex);
            queue.push(file_data);
            curr_size++;
        }
        std::cerr << "Notified!" << std::endl;
        /* Notify one of the writer threads. */
        data_in_queue.notify_one();
    }

    FileData pop_job() {
        {
            std::cerr << "Waiting for data_in_queue..." << std::endl;
            std::unique_lock<std::mutex> lock(mutex);
            data_in_queue.wait(lock, [this]{return curr_size > 0 || filter_done;});
        }
        {
            std::cerr << "Accessing queue..." << std::endl;
            mutex.lock();
            if (!queue.empty()) {
                std::cerr << "Queue not empty." << std::endl;
                /* New data in the mutex. */
                FileData fd = queue.front();
                queue.pop();
                curr_size--;
                mutex.unlock();
                /* Notify the filter thread. */
                queue_not_full.notify_one();
                return fd;
            } else if (filter_done) {
                /*
                 * The filter thread has finished AND no data in the queue.
                 * Return an empty title list signalling the caller thread to
                 * exit.
                 */
                std::cerr << "Filter done." << std::endl;
                mutex.unlock();
                /*
                 * Notify the next thread waiting for this condition, so they
                 * can all exit.
                 */
                data_in_queue.notify_one();
                return std::make_pair(0, IndexList());
            } else {
                /* Shouldn't ever get here. */
                assert(0);
            }
        }
    }

    void filtering_finished() {
        std::lock_guard<std::mutex> guard(mutex);
        filter_done = true;
    }

private:
    std::queue<FileData> queue;
    size_t max_size;
    size_t curr_size;
    bool filter_done;
    std::mutex mutex;
    std::condition_variable data_in_queue;
    std::condition_variable queue_not_full;
};

void filter_articles(zim::File& f, ZimData& zim_data, size_t documents,
                     const std::string& pattern) {
    size_t curr_num = 1;
    size_t written = 0;
    IndexList index_list;

    size_t doc_no = 0;
    for (zim::File::const_iterator it = f.begin(); it != f.end(); ++it) {
        std::string title = it->getTitle();
        if (it->getNamespace() != 'A') {
            std::cerr << "Dropping article " << title
                      << " not in namespace A..." <<  std::endl;
        } else if (it->isRedirect()) {
            std::cerr << "Dropping redirect article " << title
                      << "..." <<  std::endl;
        } else if (it->isDeleted()) {
            std::cerr << "Dropping deleted article " << title
                      << "..." <<  std::endl;
        } else if (it->getTitle().find(pattern) != std::string::npos) {
            std::cerr << "Dropping disambiguation article " << title
                      << "..." <<  std::endl;
        } else {
            if (++doc_no % 1000 == 0) {
                std::cerr << "At the " << doc_no << "th document." << std::endl;
            }
            std::cerr << "Writing article " << title << "..." << it.getIndex() << std::endl;

            index_list.push_back(it.getIndex());
            if (index_list.size() == documents) {
                zim_data.push_job(std::make_pair(curr_num++, index_list));
                index_list = IndexList();
            }
        }
    }

    /* Write the rest. */
    if (!index_list.empty()) {
        zim_data.push_job(std::make_pair(curr_num++, index_list));
    }
    zim_data.filtering_finished();
}

void write_articles_to_files(std::string input_file, ZimData& zim_data,
                             const std::string& output_dir, size_t zeroes) {
    zim::File f(input_file);
    while (true) {
        FileData fd = zim_data.pop_job();
        if (fd.second.empty()) {
            std::cerr << "Empty titles: exiting..." << std::endl;
            break;
        }
        std::cerr << "Num titles: " << fd.second.size() << std::endl;

        std::string num = std::to_string(fd.first);
        num = std::string(zeroes - num.length(), '0') + num + ".htmls.gz";
        zstr::ofstream out(fs::path(output_dir) / num,
                           std::ios::out | std::ios::binary);
        for (auto index : fd.second) {
            auto article = f.getArticle(index);
            auto blob = article.getData();
            uint32_t size = htonl(static_cast<uint32_t>(blob.size()));
            out.write(reinterpret_cast<char*>(&size), sizeof(size));
            out.write(blob.data(), blob.size());
        }
    }
}

int main(int argc, char* argv[]) {
    ArgumentParser parser(argv);
    auto args = parser.parse(argc, argv);

    try {
        zim::File f(args["input-file"].as<std::string>());
        ZimData zim_data(args["threads"].as<size_t>());
        fs::create_directory(args["output-dir"].as<std::string>());

        std::thread filter_thread(filter_articles, std::ref(f), std::ref(zim_data),
                                  args["documents"].as<size_t>(),
                                  disambig[args["language"].as<std::string>()]);
        std::vector<std::thread> writer_threads;
        for (size_t i = 0; i < args["threads"].as<size_t>(); ++i) {
            writer_threads.emplace(writer_threads.end(), write_articles_to_files,
                                   args["input-file"].as<std::string>(), std::ref(zim_data),
                                   args["output-dir"].as<std::string>(),
                                   args["zeroes"].as<size_t>());
        }

        filter_thread.join();
        std::cerr << "Filter thread joined." << std::endl;
        std::for_each(writer_threads.begin(), writer_threads.end(),
                      std::mem_fn(&std::thread::join));
        std::cerr << "Writer threads joined." << std::endl;
    } catch (const std::exception& e) {
        std::cerr << e.what() << std::endl;
    }
}
