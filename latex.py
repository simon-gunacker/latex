#!/usr/bin/python3
# coding=utf-8

"""
latex.py: parses compiled latex project to find: 

    * table of contents (with absolute/relative words per chapter and recent changes if available)
    * list of figures
    * list of tables
    * unused figures
    * unused references
    * undefined references

if called directly, this script prints all statistics.
however, the classes defined in here are also used by client and server (see client.py, server.py)

Note: 
1. The parsers used require each section to be written in a seperate file!
2. create a new file called config.py in the same directory this script is placed in. 
   in config.py, create a variable called PROJECT_PATH and set it to the path of your latex project
"""

__author__ = "Simon Gunacker"
__copyright__ = "Copyright 2018, Graz"

import re, os, pickle, datetime
from colorama import Fore, Back, Style, init
from config import PROJECT_PATH

# manually set these files to configure your project.
# they are parsed to extract the information mentioned above
AUXPATH = "%s\\auxil\\main.aux" % PROJECT_PATH
BIBPATH = "%s\\bibliography\\refs.bib" % PROJECT_PATH
TOCPATH = "%s\\auxil\\main.toc" % PROJECT_PATH
LOFPATH = "%s\\auxil\\main.lof" % PROJECT_PATH
LOTPATH =  "%s\\auxil\\main.lot" % PROJECT_PATH
CHAPTERS = "%s\\chapters" % PROJECT_PATH
FIGURES = "%s\\figures" % PROJECT_PATH
BIBLOG = "%s\\auxil\\main.blg" % PROJECT_PATH
MAINLOG = "%s\\auxil\\main.log" % PROJECT_PATH

# path to data directory storing statistics
DATADIR = "."

# used by colorama
init(autoreset=True)

# automatic variables
DATE = datetime.datetime.now().isoformat()[:10]
DATAFILE = os.path.join(DATADIR, "snapshot-{}.pkl".format(DATE))

# These patterns are used by the parsers to extract the needed information
CHAPTER = r"\\contentsline \{(chapter)\}\{\\numberline \{(\d+)\}(.*)\}\{(\d+)\}.*"
SECTION = r"\\contentsline \{(section)\}\{\\numberline \{(\d+.\d+)+\}(.*)\}\{(\d+)\}.*"
SUBSECTION = r"\\contentsline \{(subsection)\}\{\\numberline \{(\d+.\d+.\d+)+\}(.*)\}\{(\d+)\}.*"
FIGURE = r"\\contentsline \{figure\}\{\\numberline \{(\d+.\d+)\}\{\\ignorespaces (.*)\}\}\{(\d+)\}.*"
TABLE = r"\\contentsline \{table\}\{\\numberline \{(\d+.\d+)\}\{\\ignorespaces (.*)\}\}\{(\d+)\}.*"
REFERENCE = r"@.*\{(.*),"
CITATION = r".*@cite\{(.*)\}"
TEXCHAPTER = r"\\chapter\{(.*)\}"
TEXSECTION = r"\\section\{(.*)\}"
TEXSUBSECTION = r"\\subsection\{(.*)\}"
TEXFIGURES = r".*\\includegraphics.*\{(.*)\}.*"
BIBLOGWARN = r".*WARN - (.*) -.*"
MAINLOGWARN1 = r"(.*)Warning(.*)"
MAINLOGWARN2 = r"(.*)warning(.*)"
MAINLOGERR = r"(.*)Error(.*)"

# windows hack for keeping window on top (https://stackoverflow.com/questions/3926655)
def window_always_on_top():
    import win32gui, win32process, win32con
    windows = []
    win32gui.EnumWindows(lambda hwnd, windows: windows.append((win32gui.GetWindowText(hwnd),hwnd)), windows)
    try:
        window, hwnd = next(window for window in windows if window[0].lower().startswith("anaconda"))
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOMOVE)
    except StopIteration:
        pass

class AbstractParser(object):
    """
    Parses a file line by line.

    This class is not supposed to be instantiated. Subclasses should implement the _parse method
    """

    # Implement this method in any subclass
    # called on each line (by parse(self, file))
    # returns entry containing extracted information or none if line didn't match the given pattern
    _parse = lambda self, line: None

    def parse(self, file):
        """
        parses a file line by line extracting relevant information

        :returns a list of entries containing the extracted information
        :param file: the file to parse
        """
        # after the file is opened, each line is parsed by _parse
        # _parse returns an entry containing relevant information or None if line did not match the given pattern
        # all None-objects are filtered before the list is returned
        with open(file, encoding='utf-8') as f:
            return list(filter(lambda item: item is not None, [ self._parse(line) for line in f.readlines() ]))

class Parser(AbstractParser):
    """
    Parses a file line by line and extracts relevant information based on given patterns.
    """

    def __init__(self, patterns):
        """
        :param patterns: a list of patterns. Each pattern is applied on each line.
        """
        self.patterns = patterns

    def _parse(self, line):
        """
        :returns an entry containing relevant information or None if line does not match any pattern
        :param line: the current line the patterns are applied to
        """
        # matched_patterns is a list of matches found for a single line. Each line is supposed to have at most one match
        matched_patterns = map(lambda pattern: re.match(pattern, line), self.patterns)

        # matching_pattern is either an empty list if no pattern matches or a list containing the one match that has been found
        matching_pattern = list(filter(lambda matched: matched is not None, matched_patterns))

        # entry is none if no pattern matched the current line. Otherwise, entry contains a list of relevant information extracted from the line
        entry = matching_pattern[0].groups() if len(matching_pattern) > 0 else None

        return entry

class Files(object):
    """
    an os.listdir abstraction yielding both, the filename and the full path of all files (not dirs) in a directory
    """
    def __init__(self, path):
        self.path = path
    
    def __iter__(self):
        _fileinfo = lambda filename: (filename, os.path.join(self.path, filename))
        _is_path = lambda fileinfo: os.path.isfile(fileinfo[1])

        yield from filter(_is_path, map(_fileinfo, os.listdir(self.path)))

class DirParser(Parser):
    """
    parse multiple files at once.
    """
    def __init__(self, path, patterns):
        super(DirParser, self).__init__(patterns)
        self.path = path
    
    def parse(self):
        """
        iterates over all files in a given dir and parses them using the given patterns

        :returns all entries found in any file, format { filename: [ entries* ] }
        """
        # TODO: can this be reduced to a single iteration?
        results = { filename: super(DirParser, self).parse(filepath) for filename, filepath in Files(self.path) }
        return { filename: entries for filename, entries in results.items() if len(entries) > 0 }

class WordCounter(DirParser):
    """
    Parses all chapters to find the number of words per chapter.

    Can be used as a lookup table ( WordCounter[caption] -> { file, number_of_words } )
    Requires each chapter to be written in a single file.
    """

    def __init__(self, path):
        """
        inits the WordCounter. After initialization, the WordCounter contains a dict of all 
        words written for any section and the corresponding file

        :param path: see DirParser
        :param patterns: see DirParser
        """
        super(WordCounter, self).__init__(path, [TEXCHAPTER, TEXSECTION, TEXSUBSECTION])
        self.maxwords = -1
        self.entries = self.count_all_words()

    def __getitem__(self, key):
        return self.entries[key]

    def count_all_words(self):
        """
        counts the words written in each section

        :returns a dict of counts { caption -> {file: <FILENAME>, words: <NUMBER_OF_WORDS> } }
        """
        # remodel dict
        result = {}
        for filename, entries in self.parse().items():
            caption, words = entries[0][0], self.count_words(filename)
            self.maxwords = words if words > self.maxwords else self.maxwords
            result[caption] = { "file": filename, "words": words }
        return result

    def count_words(self, filename):
        # return len(open(os.path.join(self.path, filename),'r').read().split())
        words, skip_line, skipterms = 0, False, ["$$", "{align", "{equation}", "{figure}", "{table}"]
        with open(os.path.join(self.path, filename), 'r') as f:
            for line in f.readlines():
                if any(map(lambda term: term in line, skipterms)):
                    skip_line = not skip_line
                if not skip_line:
                    #if filename=="323-visualization.tex":
                    #    print(line)
                    words += len(line.split())
        return words

class AbstractFormatter(object):
    """
    Formats a list of entries.

    This class is not supposed to be instantiated. Subclasses should implement the _format method
    """

    # some methods to produce colorful output
    _color = lambda self, text: str(text) + Style.RESET_ALL + Fore.WHITE
    _green = lambda self, text: Fore.GREEN + Style.BRIGHT + self._color(text)
    _red = lambda self, text: Fore.RED + Style.BRIGHT + self._color(text)
    _gray = lambda self, text: Fore.BLACK + Style.BRIGHT + self._color(text)
    _yellow = lambda self, text: Fore.YELLOW + Style.BRIGHT + self._color(text)
    _brown = lambda self, text: Fore.YELLOW + Style.DIM + self._color(text)

    # Implement this method in any subclass
    # called on each item of the list
    _format = lambda self, i, item: str(item)

    def show(self, iterable, caption=""):
        """
        Shows formatted output.
        """
        print(self._red(caption)+"\n") if len(list(iterable)) > 0 else None
        for i, item in enumerate(iterable, start=1):
            print(self._format(i, item))
        print()

class ConstantWidthFormatter(AbstractFormatter):
    """
    Formats a list of entries in form <_indent()><_left()> ....... <_right()>
    """
    _WIDTH = 100

    # Implement these methods in subclasses
    _indent = lambda self, item: 0
    _left = lambda self, item: str(item)
    _right = lambda self, item: ""
    _extend = lambda self, item: ""

    def _format(self, i, item):
        """
        formats a single line.

        :returns the formatted string
        :param i: the number of the item
        :param item: the item (which is usually a list containing information that has to be splitted by subclasses using abstract functions)
        """
        indent, left, right, extend = self._indent(item), self._left(item), self._right(item), self._extend(item)
        dots = "." * (self._WIDTH - indent - len(left) - len(right) - 2) 
        return "{0} {1} {2} {3} {4}".format(" " * indent, left, self._gray(dots), right, extend)

class EnumerationFormatter(AbstractFormatter):
    """
    Shows the (enumerated) content of a list
    """
    _format = lambda self, i, item: self._gray("{:4d}. {}".format(i, item))

    def show(self, iterable, caption="", order=lambda iterable: iterable):
        super(EnumerationFormatter, self).show(order(iterable), caption="{} ({}):".format(caption, len(list(iterable))))

class MainlogFormatter(EnumerationFormatter):
    """
    Shows (enumerated) list of warnings
    """
    def _format(self, i, item):
        source, message = item
        message = message[2:] if message.startswith(": ") else message
        source = source.replace("Package ", "").strip()
        entry = "{:<30} {}".format(self._gray(f"[{source}]"), message)
        return super(MainlogFormatter, self)._format(i, entry)

class SingleEntryTypeFormatter(ConstantWidthFormatter):
    """
    Lists entries of same type using the format specified by parent class. 
    """
    _left = lambda self, item: "{:<5} {}".format(item[0] + ".", item[1])
    _right = lambda self, item: item[2]

class MultiEntryTypeFormatter(ConstantWidthFormatter):
    """
    Lists entries of different type using the format specified by parent class. 
    This is used for table of contents.
    Different entry types are: chapter (i), section (ii), subsection (iii)
    """
    _INDENTS = [0, 3, 8]
    _indent = lambda self, item: self._INDENTS[item[0]]
    _left = lambda self, item: "{0}. {1}".format(item[1], item[2])
    _right = lambda self, item: item[3]

class TocFormatter(ConstantWidthFormatter):
    """
    Lists toc tree with some statistics for each section
    """
    _INDENTS = [0, 3, 8]
    _indent = lambda self, item: self._INDENTS[item[0]]
    _left = lambda self, item: "{0}. {1}".format(item[1], item[2])
    _right = lambda self, item: "{}".format(item[3])
    _extend = lambda self, item: (self._words(item) + self._percent(item)) if item[4] > 10 else ""
    _words = lambda self, item: self._gray(" ({:>5} words)".format(item[4]))
    _percent = lambda self, item: self._gray(" [") + self._yellow("=" * item[5]).ljust(50 + len(self._yellow(""))) + self._gray("]")  

class DiffTocFormatter(TocFormatter):
    """
    Lists toc tree and shows changes of the day
    """
    _sumpercent = lambda self, oldamount, newamount: self._brown("=" * oldamount) + Style.RESET_ALL + self._yellow("=" * newamount) 

    # _percent and _words get unreadable using a lambda expression ;-)
    def _words(self, item):
        """
        shows overall and new words per section

        :param item: the item containing overall and new words
        """
        left, right = self._gray(" ("), self._gray(")")
        newwords = int(item[4] - item[6])
        color = self._yellow if newwords > 0 else self._gray
        return left + self._gray("{:>5} words, ").format(item[4]) + color("{:>5} new").format(newwords) + right

    # _percent = lambda self, item: self._gray(" [") + self._sumpercent(item[7], int(item[5] - item[7])).ljust(50 + len(self._sumpercent(0, 0))) + self._gray("]")
    def _percent(self, item):
        """
        shows progress bar with old and new percent of words (100% = chapter with max word count)

        :param item: the item containing overall and new words
        """
        left, right = self._gray(" ["), self._gray("]")
        old, new = item[7], int(item[5] - item[7])
        bar = self._sumpercent(old, new)
        empty_bar_len = len(self._sumpercent(0, 0)) # this is not 0 as colors are used!
        return left + bar.ljust(50 + empty_bar_len) + right

# parsing the list would be sufficient in our case but the tree might allow us to compute
# sums of words recursively.
class Tree(object):
    """
    Converts a list (parsed table of content) into a tree. Object can be iterated.
    """

    # formatting constants
    WIDTH, INDENT = 100, [0, 3, 8]

    # internal properties 
    number_of_nodes = 0

    # helper functions: get item information, check if item is child of another item
    _get_number = lambda self, item: item[1]
    _get_level = lambda self, item: self._get_number(item).count('.')
    _get_type = lambda self, item: item[0]
    _get_words = lambda self, item: item[3]
    _get_percent = lambda self, item: item[4]
    _is_chapter = lambda self, item: self._get_type(item) == 'chapter'
    _is_descendant = lambda self, item, candidate: self._get_number(candidate).startswith(self._get_number(item))
    _is_next_generation = lambda self, item, candidate: self._get_level(candidate) == self._get_level(item) + 1
    _is_child_of_item = lambda self, item, candidate: self._is_descendant(item, candidate) and self._is_next_generation(item, candidate) 
    _is_child = lambda self, item, candidate: self._is_chapter(candidate) if item is None else self._is_child_of_item(item, candidate)

    def __init__(self, table_of_content):
        """
        Initializes the toc tree by generating the tree, the lookuptable and by initializing the word counter

        :param table_of_content: the list of toc entries that is converted into a tree
        """
        self.tree = self.generate_tree(table_of_content)
        self.wc = WordCounter(CHAPTERS) # init __before__ lut!!
        self.lut = self.generate_lut(table_of_content)

    def __iter__(self):
        yield from self.get_tree()

    def __len__(self): 
        return self.number_of_nodes
    
    def get_children(self, table_of_content, node=None):
        """
        :returns a list of children for a given node or a list of root nodes if node=None
        :param table_of_content: the list of toc entries
        :param node: the node to find the children for
        """
        return [item for item in table_of_content if self._is_child(node, item)]

    def generate_tree(self, table_of_content, tree={}, current_node=None):
        """
        :returns a tree of numbers of toc entries
        :param table_of_content: the list containing all toc entries
        :param tree: the (current) (sub)tree to append children to
        :param current_node: the current child to find children for
        """
        for child in self.get_children(table_of_content, current_node):
            number = self._get_number(child)
            tree[number] = {}
            self.number_of_nodes += 1
            self.generate_tree(table_of_content, tree[number], child)
        return tree

    def generate_lut(self, table_of_content):
        """
        :returns a lookup table { caption -> toc entry }
        :param table_of_content: the list of toc entries that is converted into a lut
        """
        lut = {}
        for item in table_of_content:
            _, number, caption, page = item
            words = self.wc[caption]['words']
            percent = int(words / self.wc.maxwords * 50)
            lut[self._get_number(item)] = (number, caption, page, words, percent)
        return lut

    def get_tree(self, tree=None, level=0):
        """
        yields next tree node. Used by __iter__(self).
        """
        tree = self.tree if tree is None else tree
        for number in tree:
            yield (level, *self.lut[number])
            if len(tree[number]) > 0:
                yield from self.get_tree(tree=tree[number], level=level+1)

class DiffTree(Tree):
    """
    A tree that keeps track of changes (new words at current day)
    If no diff is given, DiffTree behaves the same way a simple Tree does.
    """

    def __init__(self, table_of_content, diff=None):
        """
        inits DiffTree

        :param table_of_content: the table to be converted into a tree
        :param diff: a snapshot of all stats when first started at the current day
        """
        super(DiffTree, self).__init__(table_of_content)
        self.diff = diff

    def __iter__(self):
        for level, number, caption, page, words, percent in self.get_tree():
            if self.diff is None:
                yield level, number, caption, page, words, percent
            else:
                oldwords = self.diff._get_words(self.diff.lut[number])
                oldpercent = self.diff._get_percent(self.diff.lut[number])
                yield (level, number, caption, page, words, percent, oldwords, oldpercent)

class Statistics(object):
    """
    Defines methods for printing latex statistics
    """

    _parse_table_of_content = lambda self: Parser([CHAPTER, SECTION, SUBSECTION]).parse(TOCPATH)
    _parse_list_of_figures = lambda self: Parser([FIGURE]).parse(LOFPATH)
    _parse_list_of_tables = lambda self: Parser([TABLE]).parse(LOTPATH)
    _parse_references = lambda self: set([ref[0] for ref in Parser([REFERENCE]).parse(BIBPATH)])
    _parse_citations = lambda self: set([cit[0] for cit in Parser([CITATION]).parse(AUXPATH)])
    _parse_biblog = lambda self: list([warn[0] for warn in Parser([BIBLOGWARN]).parse(BIBLOG)])
    _parse_mainlog = lambda self: list(filter(lambda entry: "Package:" not in entry[0], Parser([MAINLOGWARN1, MAINLOGWARN2, MAINLOGERR]).parse(MAINLOG)))
    _parse_used_figures = lambda self: set([figure[0][len('figures/'):] for figures in DirParser(CHAPTERS, [TEXFIGURES]).parse().values() for figure in figures])
    _parse_avail_figures = lambda self: set([filename.split('.')[0] for filename, _ in Files(FIGURES)])
    _compute_used_references = lambda self: self._parse_references() & self._parse_citations()
    _compute_unused_references = lambda self: self._parse_references() - self._compute_used_references()
    _compute_undefined_references = lambda self: self._parse_citations() - self._compute_used_references()
    _compute_unused_figures = lambda self: self._parse_avail_figures() - self._parse_used_figures()

    def print_table_of_content(self):
        self._print_table_of_content() if not os.path.isfile(DATAFILE) else self._print_diff_table_of_content()

    def print_list_of_figures(self):
        SingleEntryTypeFormatter().show(self._parse_list_of_figures(), caption="List of Figures")

    def print_list_of_tables(self):
        SingleEntryTypeFormatter().show(self._parse_list_of_tables(), caption="List of Tables")

    def print_unused_figures(self):
        EnumerationFormatter().show(self._compute_unused_figures(), caption="Unused figures", order=sorted)

    def print_unused_references(self):
        EnumerationFormatter().show(self._compute_unused_references(), caption="Unused references", order=sorted)
        
    def print_undefined_references(self):
        EnumerationFormatter().show(self._compute_undefined_references(), caption="Undefined references", order=sorted)

    def print_bibtex_warnings(self):
        EnumerationFormatter().show(self._parse_biblog(), caption="Bibtex warnings")

    def print_mainlog_warnings(self):
        MainlogFormatter().show(self._parse_mainlog(), caption="Mainlog warnings")

    def print_warnings(self):
        biblog = [('BibTex', entry) for entry in self._parse_biblog()]
        MainlogFormatter().show(self._parse_mainlog() + biblog, caption="All warnings")
            
    def backup_first_start_of_day(self):
        if not os.path.isfile(DATAFILE):
            self.backup(DATAFILE)

    def backup(self, path):
        with open(path, 'wb') as snapshot: pickle.dump({
                "table-of-content": Tree(self._parse_table_of_content()),
                "list-of-figures": self._parse_list_of_figures(),
                "list-of-tables": self._parse_list_of_tables(),
                "references": self._parse_references(),
                "citations": self._parse_citations(),
                "used-figures": self._parse_used_figures(),
                "avail-figures": self._parse_avail_figures()
            }, snapshot)

    def _print_table_of_content(self):
        TocFormatter().show(Tree(self._parse_table_of_content()), "Table of content")

    def _print_diff_table_of_content(self):
        with open(DATAFILE, 'rb') as snapshot: 
            info = pickle.load(snapshot)["table-of-content"]
            DiffTocFormatter().show(DiffTree(self._parse_table_of_content(), diff=info), "Table of content")

if __name__ == '__main__':
    os.system("cls")
    stats = Statistics()
    stats.print_table_of_content()
    stats.print_list_of_figures()
    stats.print_list_of_tables()
    stats.print_unused_figures()
    stats.print_unused_references()
    stats.print_undefined_references()
    stats.print_mainlog_warnings()
    stats.print_bibtex_warnings()
    stats.backup_first_start_of_day()