#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stuff used for HTML parsing."""

import re
# Pattern for recognizing headers
headerp = re.compile('[hH][0-9]+')
# Pattern for recognizing lists
listp = re.compile('[ou]l')
