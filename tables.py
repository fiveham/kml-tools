"""A module to read and write text data from/to files.

The main functions are `read` and `write`, which take pathnames
for the file to read or write, not file-like objects, and which return and
accept (respectively) a list of dicts with the same keys and whose keys are
the column headings in the file.

The expected file format is that the first line is column names and that each
subsequent line is the entries of a record. Column names and record entries
are delimited by the same delimiter (and can be made to contain the delimiter
by using a text qualifier)."""

def _anneal_by_qualifier(elements, qualifier, delim):
    """Account for delimited text by squishing adjacent elements together.

       :param elements: a list of strings
       :param qualifier: string, often '"'
       :param delim: string, often '\t' or ','
       :returns: `elements`, mutated
    """
    if qualifier:
        while any(delimited_piece.startswith(qualifier)
                  for delimited_piece in elements):
            i = next(iter(i
                          for i in range(len(elements))
                          if elements[i].startswith(qualifier)))
            j = next(iter(j
                          for j in range(i, len(elements))
                          if elements[j].endswith(qualifier)))
            elements[i] = elements[i][  len(qualifier):]
            elements[j] = elements[j][:-len(qualifier) ]
            elements[i:j+1] = [delim.join(elements[k]
                                          for k in range(i, j+1))]
    return elements

def _by_lines(line_source, delim, qualifier, translate):
    """Yield dict records from `line_source`

       :param line_source: an iterable of strings
       :param delim: the text delimiter, often '\t' or ','
       :param qualifier: string that turns on/off ignoring delimiters
       :param translate: a dict mapping from column name to a function that
       transforms the file-stored version of a value to its proper runtime form
       :returns: a generator
    """
    
    columns = []
    
    for line in line_source:
        
        if line.endswith('\n'):
            line = line[:-1]
        
        elements = _anneal_by_qualifier(
                line.split(delim), qualifier, delim)
        
        if not columns:
            columns = elements
            continue
        
        yield {c:translate.get(c, (lambda x:x))(e)
               for c, e in zip(columns, elements)}

def _read(path_name, delim, qualifier, translate):

    """Read the file at `path_name` and return its content as a list of dicts.
       
       :param path_name: name of (and path to) the file to read
       :param delim: delimiter to separate entries within a record
       :param qualifier: ignore delimiters inside a pair of these
       :param translate: dict from column name to a callable that transforms
       entries from that column"""

    #returning the generator would exit the with-clause and close the file
    with open(path_name, 'r') as outof:
        for thing in _by_lines(outof, delim, qualifier, translate):
            yield thing 

def _check_delim(path_name, kwargs, by_extension={'.txt':'\t', '.csv':','}):
    
    """Return a delimiter string based on caller input or file extension.
       
       Either extract a delimiter specified in `kwargs` as `delim`, or if
       a delimiter isn't specified that way, return a standard delimiter based
       on the file extension at the end of `path_name`. If `path_name` does
       not match any pre-defined extension-to-delimiter relationship, raise a
       ValueError, otherwise return the extracted/assumed delimiter.

       :param path_name: a string ending with the name of the file that a
       table is read from or written to
       :param kwargs: a dict of named parameters specified by the user
       calling `read()` or `write()`
       :param by_extension: a dict mapping from file extension to a
       pre-defined corresponding delimiter"""
    
    try:
        return kwargs['delim']
    except KeyError:
        pass
    
    try:
        return next(iter(
                delim
                for extension, delim in by_extension.items()
                if path_name.endswith(extension)))
    except StopIteration:
        raise ValueError('Delimiter `delim` not specified. Could not '
                         'assume based on file extension.')

def _check_qualifier(path_name, delim, kwargs):
    for q in ('qualifier', 'qual'):
        try:
            return kwargs['qualifier']
        except KeyError:
            pass
    if path_name.lower().endswith('csv'):
        first_record = next(iter(_read(path_name, delim, '', {})))
        if all(column.startswith('"') and column.endswith('"')
               for column in first_record):
            return '"'
    return ''

def read(path_name, *args, **kwargs):
    
    """Read a data table from a file specified by path_name.

       :param path_name: the name of (or path to followed by name of) the
       file to read
       
       :param delim: the delimiter used between cell entries in the table.
       Defaults to tab ('\t') for files ending in .txt and to comma (',')
       for files ending in .csv.

       :param qual: text qualifier, prepended and appended to cell entry text
       to prevent delim instance being used to delimit text

       :param qualifier: alias for qual
       
       :param translate: a dict mapping from column name to a callable (such
       as `int`, `float`, or `eval`) which translates a value in that column
       into a new form.
       """
    
    from os import PathLike
    if isinstance(path_name, PathLike):
        path_name = path_name.__fspath()
    
    delim     = _check_delim(path_name, kwargs)
    qualifier = _check_qualifier(path_name, delim, kwargs)
    translate = kwargs.get('translate', {})
    
    return list(_read(path_name, delim, qualifier, translate))

def parse(text, *args, **kwargs):
    """Parse a table from text without needing to read a file."""
    
    delim     = kwargs.get('delim',     '\t')
    qualifier = kwargs.get('qualifier', '')
    translate = kwargs.get('translate', {})

    return list(_by_lines(text.split('\n'), delim, qualifier, translate))

def _maybe_qualify(text, qualifier, delim):
    """Surround `text` with `qualifier`s if and only if `delim` is in text."""
    return text if delim not in text else f'{qualifier}{text}{qualifier}'

def write(table, path_name, *args, **kwargs):
    """Save the table to a file.
       
       :param table: a list of dicts
       :param path_name: the name of the file where `table` is saved
       """
    delim = _check_delim(path_name, kwargs)
    
    qualifier = kwargs.get('qualifier', '')
    
    with open(path_name, 'w') as into:
        columns = [a for a in table[0]]
        into.write(delim.join(_maybe_qualify(a, qualifier, delim)
                              for a in columns)+'\n')
        for record in table:
            into.write(delim.join(
                    _maybe_qualify(entry, qualifier, delim)
                    for entry in (str(record[key])
                                  for key in columns))+'\n')

class Table(list):
    """A glorified list of dicts.

       This class extends `list` and supports indexing records by their values
       in a particular column (see `Table.index_by()`) and supports accessing
       setting, and deleting entire columns. Columns can be accessed by
       subscripting the name of the column or by using the column's name as
       an attribute of the table (except when there's a real attribute with
       that name). Indexed records can be accessed by calling the table with
       the index key (the row's ostensibly unique value in whicheve column was
       used to index the table) as the sole parameter and can also be accessed
       by using the index key as an attribute of the table (Just like accessing
       columns, real attributes take precedence, and also columns take
       precedence over index keys when retrieving a non-existent attribute.).

       Subscripting the table with an int or slice (such as `1:9`) behaves
       just like an ordinary `list`, because `__getitem__` delegates to the
       superclass in those cases.
       """
 
    @staticmethod
    def read(filename, *args, **kwargs):
        """Read the file and return a Table of its contents.
           :param filename: name of or path to a file"""
        return Table(read(filename, *args, **kwargs))
    
    def __init__(self, records, **formats):
        super(Table, self).__init__(records)
        self.format(**formats)
        self.__index = {}
    
    @property
    def columns(self):
        return list(self[0].keys())
    
    def format(self, **formats):
        """Transform the types of the entries in the table.

           :param formats: a mapping from column heading to a one-param
           callable that returns a transformed version of the an entry from
           the column named by the corresponding key

           Example:
           >>> table.format(lat=float, long=float, year=int)
           """
        for record in self:
            for column, _format in formats.items():
                if column in record:
                    record[column] = _format(record[column])
    
    def by(self, column, one_to_one=False, out=None):

        """Return a dict from values in a column to matching records (list).
           
           The dict has as keys all the values from the column. Each key maps
           onto a list of the records whose value in that column is the key.

           If one_to_one is truthy, then the resulting dict maps instead onto
           the last element of the list it would have mapped onto otherwise.

           :param column: a column heading in this table
           
           :param one_to_one: if True, the returned dict maps only onto the last
           record in the table with the key value in the column

           :param out: a column heading in the table. If specified, then
           records in the values of the returned dict are replaced by those
           records' elements from the column named by `out`.
           """
        
        result = {}
        for record in self:
            key = record[column]
            if key not in result:
                result[key] = []
            result[key].append(record)
            if one_to_one and len(result[key]) > 1:
                raise ValueError("Couldn't make it one-to-one")
        
        if out is not None:
            for key,subtable in result.items():
                result[key] = [record[out] for record in subtable]
        
        if one_to_one:
            for key,subtable in result.items():
                result[key] = subtable[-1]
        return result
    
    def index_by(self, column, wrapper=(lambda x : x)):
        
        """Index from each value in `column` to the corresponding record.
           
           Set the internal index dict so that it maps from the values in
           the specified column to the the last (and ostensibly sole) record
           with that value in that column. Once this index is established,
           the indexed records can be retrieved by calling the table with
           an index key (a value from the column) as the sole parameter or
           by treating that key as an attribute of the table (notwithstanding
           real attributes and columns).

           :param column: The name of the column whose entries to use as keys
           to access the last/sole record with that value (the key) in that
           column

           :param wrapper: a callable which returns a modified version of a
           newly-computed index dict when such a dict is sent to it as its sole
           parameter. For example, a case-insensitive dict subclass.
           """
        
        self.__index = wrapper({record[column]:record for record in self})
    
    def __call__(self, key):
        """Return the record indexed from `key`
           
           Example use:
           state_table = Table(states_records)
           state_table.index_by('fips_code')
           nc_record = table('037')"""
        return self.__index[key]
    
    def __getitem__(self, column):
        """Either delegate retrieval of elements/slices to the superclass
           or return a generator that iterates over the values in the specified
           column of the table."""
        
        #If it's a valid index for a list, send to superclass
        if isinstance(column, slice) or isinstance(column, int):
            return super(Table, self).__getitem__(column)
        
        #otherwise send back the named column
        return (record[column] for record in self)
    
    def __getattr__(self, name):

        #if that's an existing column name, return the column
        #(as a generator); otherwise try to return the record
        #corresponding to that name in the index, if there is one.
        if name in self.columns:
            return self.__getitem__(name)
        else:
            return self.__index[name]
    
    def __setitem__(self, column, value):
        
        #If it's a valid index for a list, send to superclass
        if isinstance(column, slice) or isinstance(column, int):
            super(Table, self).__setitem__(column, value)
            return
        
        if len(value) != len(self):
            raise ValueError('length mismatch')
        for record,element in zip(self, value):
            record[column] = element
    
    def __delitem__(self, item):
        """Delete the column or else delete the index/slice.
           
           If `item` is an int or slice, delegate to superclass. Otherwise,
           assume `item` is a column heading and try to remove `item` as a key
           from every record.

           :param item: an int index, a slice, or a column name"""
        
        #If it's a valid index for a list, send to superclass
        if isinstance(item, slice) or isinstance(item, int):
            super(Table, self).__setitem__(item, value)
        
        for record in self:
            del record[item]
    
    def __delattr__(self, name):
        """Delegate to `__delitem__`. `del table.a` means `del table['a']`."""
        del self[name]


def _clean_(piece):
	piece = piece.strip()
	a = 1 if piece.startswith('"') else None
	b = -1 if piece.endswith('"') else None
	return piece[a:b]

def _split_(line):
	ignore_comma = False
	pieces = []
	piece = ''
	for c in line:
		if c == '"':
			ignore_comma = not ignore_comma
			piece += c
		elif c == ',' and not ignore_comma:
			pieces.append(clean(piece))
			piece = ''
		else:
			piece += c
	else:
		pieces.append(clean(piece))
	return pieces

def _to_table_(file):
	with open(file) as outof:
		columns = []
		table = []
		for line in outof:
			if line.endswith('\n'):
				line = line[:-1]
			elements = split(line)
			if not columns:
				columns = elements
				continue
			table.append({columns[i]:elements[i] for i in range(max(len(elements),len(columns)))})
		return table

def pretty_print(table):
    try:
        columns = table.columns
    except:
        columns = list(table[0])
    else:
        columns = list(columns)

    rows = [[str(record[column]) for column in columns] for record in table]
    widths = [max(len(row[i]) for row in rows) for i in range(len(columns))]
    for row in rows:
        for item, width in zip(row, widths):
            print(item, end=(' '*(1 + width - len(item))))
        print()
