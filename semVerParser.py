#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
@author: sg30983
"""

import os
import re
import sys
import requests
from pkgutil import get_importer, ImpImporter
from HTMLParser import HTMLParser


WINDOWS = sys.platform.startswith("win") or\
    (sys.platform == 'cli' and os.name == 'nt')


DIST_REGEX = re.compile(r'(?P<pkgName>[^-]+)-(?P<version>[^-]+)')
VERSION_REGEX =\
    re.compile(r'(?P<major>[^-]+)\.(?P<minor>[^-]+)\.(?P<patch>[^-]+)')

def find_dist(path):
    ''' find distributions '''
    dist_dict = {}
    if os.path.isdir(path) and os.access(path, os.R_OK):
        path_item = os.listdir(path)
        for item in path_item:
            pkg_name, version = [None] * 2
            item_lower = item.lower()
            if item_lower.endswith('.dist-info'):
                item, _ = os.path.splitext(item)
                match = DIST_REGEX.match(item)
                if match:
                    pkg_name, version =\
                        DIST_REGEX.match(item).group('pkgName', 'version')
            dist_dict = dict(dist_dict.items() + {pkg_name: version}.items())
    return dist_dict

def _mro_getter(cls):
    ''' get_obj_mro '''
    if not isinstance(cls, type):
        class Cls(cls, object):
            ''' class defined in-order to get mro from object '''
            pass
        return Cls.__mro__[1:]
    return cls.__mro__

def comparison_func(a, b):
    ''' Returns Value based on comparison operator '''
    if a == b:
        result = 0
    elif a < b:
        result = -1
    else:
        result = 1
    return result

def parse(version):
    ''' parses version to get major, minor and patch '''
    match = VERSION_REGEX.match(version)
    if match is None:
        raise VersionParseException('Version Could not be parsed')
    major, minor, patch = match.groups()
    return (int(x) for x in [major, minor, patch])

DIST_FINDER_DICT = {ImpImporter: find_dist}

class PkgNameNotFoundException(ValueError):
    ''' PkgNotFoundException '''
    pass


class VersionParseException(ValueError):
    ''' VersionParseException '''
    pass


class ImplementationError(Exception):
    ''' ImplementationError '''
    def __init__(self, message):
        super(ImplementationError, self).__init__(message)
        self.message = message


class HTTPRequestException(Exception):
    ''' HTTPRequestException '''
    pass


class Singleton(type):
    ''' A singleton pattern '''

    __instance = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls.__instance:
            cls.__instance[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls.__instance[cls]


class PackageVersion(object):
    ''' PackageVersion '''

    __metaclass__ = Singleton

    def __init__(self, entries=None):
        self.entries = []
        self.importer_dict = {}
        self.distribution = {}
        if entries is None:
            self.entries = sys.path
        for entry in self.entries:
            self._add_importer_name(entry)
        self.load_distribution()

    def _add_importer_name(self, entry):
        ''' add_pkg_name '''
        importer = get_importer(entry)
        self.importer_dict[entry] = importer

    @staticmethod
    def get_finder_func(obj):
        ''' get_finder_func '''
        for mro in _mro_getter(getattr(obj, '__class__', type(obj))):
            if mro in DIST_FINDER_DICT:
                return DIST_FINDER_DICT[mro]
        return None

    def load_distribution(self):
        ''' load_distribution '''
        for path, importer in self.importer_dict.iteritems():
            finder_func = self.get_finder_func(importer)
            if finder_func:
                dist_dict = finder_func(path)
                self.distribution =\
                    dict(self.distribution.items() + dist_dict.items())

    def __iter__(self):
        '''
           Iterate over the distibution dict containing distibution name and
           version number.
        '''
        if len(self.distribution == 0):
            raise ImplementationError('Need to run public method'
                                      '`load_distribution` on instance first')
        for key, value in self.distribution.iteritems():
            if value:
                item = (key, value)
                yield item

    @property
    def size(self):
        ''' Return size of distribution dict '''
        return len(self.distribution)


class ContextPackage(object):
    ''' ContextPackage '''

    WIN_PACKAGE_REGEX =\
        re.compile(r'(.*\\+)(?P<pkgName>[a-zA-Z-]+)(\\+__init__\.py[c]?\'>$)')
    LINUX_PACKAGE_REGEX =\
        re.compile(r'(.*\/)(?P<pkgName>[a-zA-Z-]+)(\/__init__\.py[c]?\'>$)')

    def __init__(self, pkgFilePath):
        self.pkgName = self._get_pkg_name(pkgFilePath)
        self.distribution_set = PackageVersion().distribution
        self._version = self._find_version()

    def _get_pkg_name(self, packageFilePath):
        ''' get package name '''
        if WINDOWS:
            match = self.WIN_PACKAGE_REGEX.match(packageFilePath)
        else:
            match = self.LINUX_PACKAGE_REGEX.match(packageFilePath)
        try:
            return match.group('pkgName')
        except AttributeError:
            raise PkgNameNotFoundException

    def _find_version(self):
        ''' _find_version '''
        try:
            version = self.distribution_set[self.pkgName]
        except KeyError:
            version = '0.0.0'
        return version

    def __str__(self):
        ''' String rep '''
        try:
            version = getattr(self, '_version', None)
        except ValueError:
            version = 'Unknown'
        return '%s %s' % (self.pkgName, version)

    def __repr__(self):
        ''' __repr__ '''
        return "<PKG-NAME>: %s <VERSION>: %s" % (self.pkgName, self._version)

    def _get_zipped_list_for_version_compare(self, other):
        ''' _get_zipped_list_for_version_compare '''
        if not other.version:
            raise ValueError('Version for other %s could not be found' % other)
        zippedList = zip(parse(self._version), parse(other.version))
        return zippedList

    def _compare_versions(self, other):
        ''' iterate_zipped_list '''
        zippedList = self._get_zipped_list_for_version_compare(other)
        for self_field, other_field in zippedList:
            compareResult = comparison_func(self_field, other_field)
            if compareResult != 0:
                return compareResult
        return 0

    def _execute_comparison_funcs(self, other, func):
        ''' _execute_comparison_funcs '''
        comparisonResult = self._compare_versions(other)
        return func(comparisonResult)

    def __eq__(self, other):
        ''' compare equal '''
        return self._execute_comparison_funcs(other, lambda x: x == 0)

    def __ne__(self, other):
        ''' compare not equal '''
        return self._execute_comparison_funcs(other, lambda x: x != 0)

    def __gt__(self, other):
        ''' compare greater than '''
        return self._execute_comparison_funcs(other, lambda x: x > 0)

    def __lt__(self, other):
        ''' compare less than '''
        return self._execute_comparison_funcs(other, lambda x: x < 0)

    def __ge__(self, other):
        ''' compare greater than equal to '''
        return self._execute_comparison_funcs(other, lambda x: x >= 0)

    def __le__(self, other):
        ''' compare less than equal to '''
        return self._execute_comparison_funcs(other, lambda x: x <= 0)


class TextParser(HTMLParser):
    ''' TextParser '''
    PARSER_REGEX = re.compile(r'.*whl$')

    def __init__(self):
        # No super call as HTMLParser in not a new-style class
        HTMLParser.__init__(self)
        self.pkgData = []

    def handle_data(self, data):
        ''' Concrete implementation for abstract method in Base Class '''
        match = self.PARSER_REGEX.match(data)
        if match:
            self.pkgData.append(data)


class ExternalPackage(object):
    ''' ExternalPackage '''

    PKG_URL = r"https://artifactory.deere.com/list/pypi-local/{0}/"
    VERSION_REGEX = re.compile(r'[^-]+-(?P<version>[^-]+\.[^-]+\.[^-]+).*')

    def __init__(self, pkgName):
        self.pkgName = pkgName
        self.session = requests.Session()
        self.parser = TextParser()
        self.version = self._get_version()

    def _parse_package_info(self):
        ''' _get_package_info '''
        httpData = self._get_http_data()
        self.parser.feed(httpData)

    def _get_http_data(self):
        ''' _get_http_data '''
        try:
            return self.session.get(self.PKG_URL.format(self.pkgName))
        except (requests.HTTPError, requests.ConnectionError):
            raise HTTPRequestException('Could not connect to URL %s'
                                       'to fetch data' % self.PKG_URL)

    @classmethod
    def arrange_items(cls, item):
        ''' arrange_items '''
        try:
            version = cls.VERSION_REGEX.match(item).group('version')
        except IndexError:
            version = None
        return version

    def _get_latest_package_version(self):
        ''' _get_latest_package_version '''
        sortedData = sorted(self.parser.pkgData, key=self.arrange_items,
                            reverse=True)
        return sortedData[0]

    def _get_version(self):
        ''' _get_version '''
        self._parse_package_info()
        latestAvailablePackage = self._get_latest_package_version()
        version =\
            self.VERSION_REGEX.match(latestAvailablePackage).group('version')
        return version
