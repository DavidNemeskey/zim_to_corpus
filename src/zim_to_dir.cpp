/**
 * \file zim_to_dir.cpp
 * \author David Mark Nemeskey
 * \version 1.0
 * \copyright Code is released under the MIT license.
 *
 * Converts a static Wikipedia HTML dump in a .zim file to a directory of files.
 *
 * For more information, read the command-line help.
 */
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
#include "spdlog/spdlog.h"
#include "spdlog/sinks/stdout_sinks.h"
#include "zstr.hpp"
#include <zim/zim.h>
#include <zim/file.h>
#include <zim/fileiterator.h>

namespace fs = std::filesystem;

/** Holds disambiguation patterns in titles for languages we support. */
std::map<std::string, std::string> disambig = {
    {"hu", "\\(egyértelműsítő lap\\)$"}, {"en", "\\(disambiguation\\)$"}
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
                ("p,pattern", "when parsing anything other than Wikipedia, "
                              "specify the regex pattern used to filter "
                              "articles (e.g. '(cover)$' for Project "
                              "Gutenberg).",
                 cxxopts::value<std::string>()->default_value(""))
                ("d,documents", "the number of articles saved into a "
                                "single output file",
                 cxxopts::value<size_t>()->default_value("2500"))
                ("Z,zeroes", "the number of zeroes in the output files' names.",
                 cxxopts::value<size_t>()->default_value("4"))
                ("T,threads", "the number of parallel threads to use.",
                 cxxopts::value<size_t>()->default_value("10"))
                ("L,log-level", "the logging level. One of "
                                "{critical, error, warn, info, debug, trace}.",
                 cxxopts::value<std::string>()->default_value("info"))
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
            if (args["pattern"].as<std::string>().size() == 0) {
                if (!disambig.count(language)) {
                    std::cout << "Language '" << language << "' is no supported. "
                              << "Choose between 'en' and 'hu'." << std::endl;
                }
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


/** List the indices of valid WP articles. */
#ifdef ARTICLE_SIZE_TYPE
#define ARTICLE_INDEX_TYPE zim::size_type
#else
#define ARTICLE_INDEX_TYPE zim::article_index_type
#endif
typedef std::vector<ARTICLE_INDEX_TYPE> IndexList;
/**
 * The name (number) of the file and the titles of the articles it should
 * contain.
 */
typedef std::pair<size_t, IndexList> FileData;


/**
 * The communication channel between the filter and writer threads.
 *
 * The threads communicate via a queue and event variables.
 */
struct ZimData {
    ZimData(size_t num_threads) : max_size(num_threads), filter_done(false) {
    }

    /**
     * Pushes a "job" (output file number and list of valid articles) to the
     * communication queue.
     *
     * \param logger the logger of the calling thread.
     */
    void push_job(FileData file_data,
                  const std::shared_ptr<spdlog::logger>& logger) {
        {
            logger->trace("Waiting on queue_not_full...");
            std::unique_lock<std::mutex> lock(mutex);
            queue_not_full.wait(lock, [this]{return queue.size() < max_size;});

            logger->trace("Pushing job...");
            queue.push(file_data);
        }
        logger->trace("Notified writers.");
        /* Notify one of the writer threads. */
        data_in_queue.notify_one();
    }

    /**
     * Pops a "job" (output file number and list of valid articles) from the
     * communication queue.
     *
     * \param logger the logger of the calling thread.
     */
    FileData pop_job(const std::shared_ptr<spdlog::logger>& logger) {
        {
            logger->trace("Waiting for data in queue...");
            std::unique_lock<std::mutex> lock(mutex);
            data_in_queue.wait(lock, [this]{return !queue.empty() || filter_done;});

            logger->trace("Accessing queue...");
            if (!queue.empty()) {
                logger->trace("Queue not empty; popping...");
                /* New data in the mutex. */
                FileData fd = queue.front();
                queue.pop();
                /* Notify the filter thread. */
                queue_not_full.notify_one();
                return fd;
            } else if (filter_done) {
                /*
                 * The filter thread has finished AND no data in the queue.
                 * Return an empty title list signalling the caller thread to
                 * exit.
                 */
                logger->trace("Filter done; notifying next writer...");
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
    bool filter_done;
    std::mutex mutex;
    std::condition_variable data_in_queue;
    std::condition_variable queue_not_full;
};

/** Creates a logger with the same level and sink as the main logger. */
std::shared_ptr<spdlog::logger> create_logger(const std::string& name) {
    auto main_logger = spdlog::get("main");
    auto logger = std::make_shared<spdlog::logger>(name, main_logger->sinks()[0]);
    logger->set_level(main_logger->level());
    return logger;
}

/**
 * The function run by the filter thread.
 *
 * Iterates through the zim file and filters deleted, redirect and
 * disambiguation pages, keeping only valid articles. Assembles \p document
 * long batches of their indices and sends them to the writer threads.
 *
 * Filtering is done in a separate thread as it is inherently sequential, but
 * very fast. The multithreaded setup allows us to quickly identify valid
 * articles and then process them parallelly in the writer threads.
 *
 * \param f the input zim file.
 * \param zim_data the communication channel between the filter and writer
 *                 threads.
 * \param documents the number of documents in a single output file.
 * \param pattern a regex to recognize pages to drop (for Wikipedia:
 *                disambiguation pages).
 */
void filter_articles(zim::File& f, ZimData& zim_data, size_t documents,
                     const std::regex& pattern) {
    auto logger = create_logger("filter");

    size_t curr_num = 1;
    size_t written = 0;
    IndexList index_list;

    for (zim::File::const_iterator it = f.begin(); it != f.end(); ++it) {
        if (it.getIndex() % 10000 == 0) {
            logger->debug("Filtering document no {}...", it.getIndex());
        }
        std::string title = it->getTitle();
        if (it->getNamespace() != 'A') {
            logger->debug("Dropped article {} not in namespace A.", title);
        } else if (it->isRedirect()) {
            logger->debug("Dropped redirect article {}.", title);
        } else if (it->isDeleted()) {
            logger->debug("Dropped deleted article {}.", title);
        } else if (std::regex_search(title, pattern)) {
            logger->debug("Dropped article {} for matching pattern.", title);
        } else {
            logger->debug("Keeping article {}.", title);

            index_list.push_back(it.getIndex());
            if (index_list.size() == documents) {
                zim_data.push_job(std::make_pair(curr_num++, index_list), logger);
                index_list = IndexList();
            }
        }
    }

    /* Write the rest. */
    if (!index_list.empty()) {
        zim_data.push_job(std::make_pair(curr_num, index_list), logger);
    }
    zim_data.filtering_finished();

    logger->info("Filtering done. Kept {} articles out of {}.",
                 (curr_num - 1) * documents + index_list.size(),
                 f.getCountArticles());
}

/**
 * The function run by the document writer threads.
 *
 * Takes a list of article indices produced by the filter thread, reads the
 * corresponding articles from the zim file and writes them into a file in the
 * output directory.
 *
 * \param id the id of the writer thread -- for identification.
 * \param input_file the name of the input file. Each writer thread creates
 *                   their own \c zim::File object over the file, as
 *                   \c zim::File is not thread-safe.
 * \param zim_data the communication channel between the filter and writer
 *                 threads.
 * \param output_dir the output directory.
 * \param zeroes the minimum number of digits in the output files' names,
 *               padded with zeroes.
 */
void write_articles_to_files(size_t id, std::string input_file, ZimData& zim_data,
                             const std::string& output_dir, size_t zeroes) {
    auto logger = create_logger("writer-" + std::to_string(id));
    zim::File f(input_file);
    while (true) {
        FileData fd = zim_data.pop_job(logger);
        if (fd.second.empty()) {
            logger->info("No more articles to write; exiting...");
            break;
        }

        std::string num = std::to_string(fd.first);
        num = std::string(zeroes - num.length(), '0') + num + ".htmls.gz";
        logger->info("Writing file {} with {} titles...", num, fd.second.size());
        zstr::ofstream out(fs::path(output_dir) / num,
                           std::ios::out | std::ios::binary);
        for (auto index : fd.second) {
            auto article = f.getArticle(index);
            logger->debug("Writing title {} to {}...", article.getTitle(), num);
            auto blob = article.getData();
            uint32_t size = htonl(static_cast<uint32_t>(blob.size()));
            out.write(reinterpret_cast<char*>(&size), sizeof(size));
            out.write(blob.data(), blob.size());
        }
    }
}


/**
 * Creates the regex object used to filter pages. If \p pattern is specified,
 * it is converted to a regex as-is; otherwise, the per-language Wikipedia
 * patterns are used.
 *
 * \param pattern a valid regex pattern.
 * \param language the Wikipedia language chosen by the user.
 */
std::regex create_pattern_regex(const std::string& custom_pattern,
                                const std::string& language) {

    std::string pattern = custom_pattern.size() > 0 ? custom_pattern
                                                    : disambig[language];
    spdlog::get("main")->debug("Pattern: ``{}``", pattern);
    try {
        return std::regex(pattern);
    } catch (const std::regex_error& e) {
        std::cerr << "Error parsing pattern: " << e.what() << std::endl;
        exit(2);
    }
}


int main(int argc, char* argv[]) {
    ArgumentParser parser(argv);
    auto args = parser.parse(argc, argv);

    auto sink = std::make_shared<spdlog::sinks::stderr_sink_mt>();
    auto logger = std::make_shared<spdlog::logger>("main", sink);
    logger->set_level(spdlog::level::from_str(args["log-level"].as<std::string>()));
    spdlog::register_logger(logger);

    std::regex pattern_regex = create_pattern_regex(
        args["pattern"].as<std::string>(), args["language"].as<std::string>());

    try {
        zim::File f(args["input-file"].as<std::string>());
        ZimData zim_data(args["threads"].as<size_t>());
        fs::create_directory(args["output-dir"].as<std::string>());

        std::thread filter_thread(filter_articles, std::ref(f), std::ref(zim_data),
                                  args["documents"].as<size_t>(), pattern_regex);
        std::vector<std::thread> writer_threads;
        for (size_t i = 0; i < args["threads"].as<size_t>(); ++i) {
            writer_threads.emplace(writer_threads.end(),
                                   write_articles_to_files, i + 1,
                                   args["input-file"].as<std::string>(),
                                   std::ref(zim_data),
                                   args["output-dir"].as<std::string>(),
                                   args["zeroes"].as<size_t>());
        }

        filter_thread.join();
        logger->trace("Filter thread joined.");
        std::for_each(writer_threads.begin(), writer_threads.end(),
                      std::mem_fn(&std::thread::join));
        logger->trace("Writer threads joined.");
    } catch (const std::exception& e) {
        logger->critical(e.what());
    }
}
