"""A helper to handle KML files as bs4.BeautifulSoup XML documents."""

from bs4.element import CData, NavigableString, Tag
from bs4 import BeautifulSoup

_OPEN = open

REPLACE = {'<': '&lt;',
           '>': '&gt;',
           '&': '&amp;'}

def _as_html(string):
    """Return a copy of `string` where all less-thans, greater-thans, 
       and ampersands are replaced by their HTML character entity equivalents.
       
       `string` : a string"""
    
    for k,v in REPLACE.items():
        string = string.replace(k,v)
    return string

def format(soup, no_empty=False):
    """Remove all leading and trailing whitespace on all strings in `soup`, 
       remove all empty or self-terminating tags, remove all kml: prefixes 
       from all tags, and ensure that all CDATA tags are properly wrapped in
       CData objects.
       
       This function modifies the `soup` object.
       
       `soup` : a KML document (bs4.BeautifulSoup)
       
       CDATA in KML gets parsed correctly when read from text, but when that
       CDATA text is put into string representations of the tag it's
       in, it is blindly given HTML entity substitution instead of being
       wrapped in "<![CDATA[...]]>"

       This function hunts down CDATA strings in `soup` and replaces them with
       bs4.element.CData objects so that they print in the "<![CDATA[...]]>"
       form.
       
       A KML document when converted to a string will often "kml:" prefixes on
       every tag. A KML file like that opens perfectly in Google Earth,
       but the Google Maps Javascript API's KmlLayer class insists that those
       make the file an "INVALID_DOCUMENT".

       This function checks every single tag and removes the "kml" prefix if it
       is present.
       
       There is never any reason for whitespace padding at the front or end of
       a string in a tag in a KML document. Similarly, pure-whitespace strings
       have no meaning in a kml document.

       This function checks every string in `soup`, replaces trimmable strings
       with their trimmed counterparts, and outright removes pure-whitespace
       strings.
       
       Empty or self-terminating tags do nothing in a KML document. This
       function checks every tag and removes the empty/self-terminating
       ones.

       :param soup: a KML document (bs4.BeautifulSoup)

       :param no_empty: if True, remove empty tags. Default False."""
    
    strip = []
    destroy = []
    for e in soup.descendants:
        if isinstance(e, NavigableString):
            if e.isspace():
                destroy.append(e) #remove empty strings
            elif e.strip() != e:
                strip.append(e) #trim trimmable strings
        elif isinstance(e, Tag):
            if e.prefix == "kml":
                e.prefix = None #remove kml: prefixes
            if e.string and e.string.parent is e: #.string works indirectly
                e.string = e.string.strip() #trim some trimmable strings
                if any(c in e.string for c in REPLACE):
                    cdata = CData(e.string)
                    if len(str(cdata)) <= len(_as_html(e.string)):
                        e.string = cdata #use CDATA to wrap HTML
    for d in destroy:
        d.extract()
    for s in strip:
        s.replace_with(s.strip())
    if no_empty:
        for tag in soup(lambda thing : isinstance(thing,Tag) and
                        len(list(thing.contents)) == 0):
            tag.decompose()

def formatted(soup):
    """Format `soup` and return it. Convenience function wrapping `format`.
    
       `soup` : a KML document (bs4.BeautifulSoup)"""
    
    format(soup)
    return soup

def get_data(pm, name):
    """Find a `<Data>` or `<SimpleData>` element in `pm` having the specified
       `name` attribute and return the element's value. Raise ValueError if no
       such data element is found.
       
       `pm` : a KML element (bs4.element.Tag), preferably a Placemark
       `name` : value of the "name' attribute of a data tag in `pm`"""
    if not isinstance(name, str) and hasattr(name, __iter__):
        return [get_data(pm, n) for n in name]
    val = pm.find(lambda tag : tag.name in ('Data','SimpleData') and
                  'name' in tag.attrs and
                  tag['name'] == name)
    if val is not None:
        return (val.value
                if val.name == "Data"
                else val).string.strip()
    raise ValueError("Data/SimpleData not found: name='"+str(name)+"'")

def add(tag, name, soup=None):
    """Create a new `name` tag and append it to `tag`. If `name` is a list,
       append the first name to `tag`, append the second name to the first, and
       so on, which is useful for creating Placemarks, since their geometry
       often looks like <Polygon><outerBoundaryIs><LinearRing><coordinates>...
       </coordinates></LinearRing></outerBoundaryIs></Polygon>

       Return the newly created (or most newly created) child tag."""
    
    soup = soup or (tag
                    if tag.parent is None
                    else next(iter(parent
                                   for parent in tag.parents
                                   if parent.parent is None)))
    if isinstance(name, list):
        pointer = tag
        for n in name:
            pointer = add(pointer, n, soup=soup)
        return pointer
    new = soup.new_tag(name)
    tag.append(new)
    return new

_SOUP_STOCK = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<kml xmlns="http://www.opengis.net/kml/2.2"'
               ' xmlns:gx="http://www.google.com/kml/ext/2.2"'
               ' xmlns:kml="http://www.opengis.net/kml/2.2"'
               ' xmlns:atom="http://www.w3.org/2005/Atom">'
               '<Document>'
               '</Document>'
               '</kml>')

def new_soup(name=None, src=_SOUP_STOCK):
    """Create and return a new KML soup (bs4). This is a convenience method to
       avoid repetitive boilerplate.
       
       `name` : a name to be added to the `<Document>` tag of the soup as the
                text of a `<name>` tag.
       `src` : a string of valid KML text"""
    
    soup = BeautifulSoup(src, 'xml')
    if name is not None:
        add(soup.Document, 'name').string = name
    format(soup)
    return soup

def coords_from_tag(coordinates_tag, first_n_coords=2):
    """Return a list of x,y or x,y,z tuples of points from the string of the
       specified <coordinates> tag.

       `coordinates_tag` : a KML <coordinates> element"""
    return [tuple([float(dim) for dim in chunk.split(',')][:first_n_coords])
            for chunk in coordinates_tag.string.strip().split()]

def open(filepath):
    """Opens the specified file as a KML document (bs4.BeautifulSoup) and
       returns it

       `filepath` : the name of or relative path to a KML file"""
    return formatted(BeautifulSoup(_OPEN(filepath), 'xml'))

def save(soup, filepath):
    """Save `soup` to a file at `filepath`

       `soup` : a KML document (bs4.BeautifulSoup)
       `filepath` : the name of the file to save"""
    _OPEN(filepath, 'w').write(str(soup))

def dock(soup, decimals=6, dims=2):
    """Reduce the number of digits in the decimal tail of floating point
       figures in <coordinates> tags to at most `decimals`.
       E.g. 10.123456789 -> 10.12345

       `soup` : a KML document (bs4.BeautifulSoup) or element
       `decimals` : the max number of digits allowed after the integer part of
                    a number"""
    import rounding
    for coordinates_tag in soup("coordinates"):
        coordinates_tag.string = ' '.join(
                ','.join(rounding.float(dim, decimals)
                         for dim in chunk.split(',')[:dims])
                for chunk in coordinates_tag.string.strip().split())

_BLURPGRELLOW = {1 : 'http://maps.google.com/mapfiles/kml/paddle/blu-circle.png',
                 2 : 'http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png',
                 3 : 'http://maps.google.com/mapfiles/kml/paddle/grn-circle.png',
                 4 : 'http://maps.google.com/mapfiles/kml/paddle/purple-circle.png'}

_GREEN_ORANGE = {1 : '7fa8d7b6',
                 2 : '7f065fb4',
                 3 : '7f4fa86a',
                 4 : '7f6bb2f6'}

def color(soup,
          scale=None,
          probe_factor=1000,
          colorize=_GREEN_ORANGE,
          icons=_BLURPGRELLOW):
    """Color the polygons of the map with four colors.
       
       :param soup: a KML document (bs4.BeautifulSoup)
       
       :param scale: If specified, the scale of the lat-long mesh used to index
       the space around the placemarks in `soup` when determining fuzzy
       neighbors. If not specified, fuzzy neighbor relationship are not
       assessed and only seamless neighbors are used to determine the coloring
       graph. The scale if specified is the exponent of two in the denominator
       by which the 360 degrees of width and 180 degrees of height of the
       earth's surface are divided to determine the boundaries of the cells
       of the indexing mesh.
       
       :param probe_factor: Divide the minimum distance between two adjacent
       vertices on any stokes boundary by this factor to get the length of the
       line segment crossing the midpoint of any stokes-remaining side used to
       empirically determine adjacency of polygons from `soup`. Used only for
       fuzzy neighbor assessment.
       
       :param colorize: a dict from small ints (colors) to their aabbggrr
       color codes (without a # symbol)

       :param icons: a dict from colors to the urls of icons"""

    #Only import these things inside this function so that if these resources
    #are not available, the rest of the script can still work
    import color_graph
    from neighboring import fuzzy, seamless
    from point_in_polygon import Polygon
    
    #Get a list of the soup's Placemarks in Polygon form
    pms = soup("Placemark")
    
    pm_polygons = [Polygon.from_kml(pms[i], info=i) for i in range(len(pms))]
    
    #describe how the polygons connect to one another by combining the graph
    #of connections based on perfectly shared sides with the graph of
    #connections based on point-in-polygon testing of probe points placed
    #on opposite sides of sides that are not shared between polygons.
    graph = seamless(pm_polygons)

    if scale is not None:
        graph |= fuzzy(pm_polygons, probe_factor=probe_factor, scale=scale)
    
    #Obtain a coloring of that graph
    coloring = color_graph.color(graph)
    
##    #Apply those color assignments as <styleUrl>s and build a set of all
##    #applied color styles
##    ids = set()
##    for i in range(len(pms)):
##        pm = pms[i]
##        url = f'#color{coloring[i]}'
##        (pm.styleUrl or add(pm, 'styleUrl')).string = url
##        ids.add(url[1:]) #strip the # symbol off
##    
##    #Remove all existing Styles or StyleMaps with the same id/url as the
##    #styleUrls applied in the previous step
##    for style in soup(['Style', 'StyleMap']):
##        if 'id' in style.attrs and style['id'] in ids:
##            style.decompose()
##    
##    #Add a Style to the soup for each style id/url used
##    for i in sorted(ids):
##        style = soup.new_tag('Style')
##        soup.Document.insert(0, style)
##        style['id'] = i
##        add(style, ['PolyStyle', 'color']).string = colorize[int(i[-1])]
##        add(style, ['LineStyle', 'color']).string = '7fcccccc'
##        add(style, ['IconStyle', 'Icon', 'href']).string = icons[int(i[-1])]

    apply_color(soup, coloring, colorize=colorize, icons=icons)
    return

def apply_color(soup, coloring, colorize=_GREEN_ORANGE, icons=_BLURPGRELLOW):
    pms = soup("Placemark")
    
    #Apply those color assignments as <styleUrl>s and build a set of all
    #applied color styles
    ids = set()
    for i in range(len(pms)):
        pm = pms[i]
        url = f'#color{coloring[i]}'
        (pm.styleUrl or add(pm, 'styleUrl')).string = url
        ids.add(url[1:]) #strip the # symbol off
    
    #Remove all existing Styles or StyleMaps with the same id/url as the
    #styleUrls applied in the previous step
    for style in soup(['Style', 'StyleMap']):
        if style.has_attr('id') and style['id'] in ids:
            style.decompose()
    
    #Add a Style to the soup for each style id/url used
    for i in sorted(ids):
        style = soup.new_tag('Style')
        soup.Document.insert(0, style)
        style['id'] = i
        add(style, ['PolyStyle', 'color']).string = colorize[int(i[-1])]
        add(style, ['LineStyle', 'color']).string = '7fcccccc'
        add(style, ['IconStyle', 'Icon', 'href']).string = icons[int(i[-1])]
    
    return

def spatial_index(soup, scale=16):
    pms = soup('Placemark')
    index = {}
    for i in range(len(pms)):
        pm = pms[i]
        
        #Find out what cells are needed to cover the Placemark
        cells = _spatial_index(pm, scale)
        
        #add mappings from each of those cells to the current Placemark
        #into the index
        for cell in cells:
            try:
                pool = index[cell]
            except KeyError:
                index[cell] = pool = set()
            pool.add(i)
    return index

def spatial_index_stats(soup, index):
    stats = [len(v) for v in index.values()]
    avg = sum(stats) / len(stats)
    m,M = min(stats), max(stats)

    max_index = len(stats) - 1
    if max_index % 2 == 0:
        med_index = max_index // 2
        median = sorted(stats)[med_index]
    else:
        med_index_lo = max_index // 2
        med_index_hi = med_index_lo + 1
        median = set(sorted(stats)[med_index_lo:(med_index_hi + 1)])
        if len(median) == 1:
            median = median.pop()
        else:
            median = sorted(median)
        #med_index = slice(med_index_lo, med_index_hi+1)
        #median = sorted(stats)[med_index]

    _range = M - m

    stdev = (sum((stat - avg)**2 for stat in stats) / len(stats)) ** 0.5

    return {'avg':avg, 'stdev':stdev, 'median':median, 'min':m, 'max':M,
            'range':_range, 'data':stats}

def _spatial_index(pm, scale):
    try:
        return next(iter(
                f(tag, scale)
                for tag, f in ([pm.find(name), func]
                               for name, func in _TAG_TO_FUNCTION.items())
                if tag))
    except StopIteration:
        raise ValueError('Placemark has no Point, LineString, Polygon, or '
                         'MultiGeometry')

def _spdx_pg(pg, scale):
    outer = coords_from_tag(pg.outerBoundaryIs.coordinates)
    cells = _cells(outer, 2, scale)
    for ibi in pg('innerBoundaryIs'):
        inner = coords_from_tag(ibi.coordinates)
        hole_rim  = _cells(inner, 1, scale)
        hole_fill = _cells(inner, 2, scale, boundary_cells=hole_rim)
        cells -= (hole_fill - hole_rim)
    return cells

def _spdx_ls(ls, scale):
    return _cells(coords_from_tag(ls.coordinates), 1, scale)

def _spdx_pt(pt, scale):
    return _cells(coords_from_tag(pt.coordinates)[0], 0, scale)

def _spdx_mg(mg, scale):
    cells = set()
    for geom in mg(list(_TAG_TO_FUNCTION)):
        cells.update(_TAG_TO_FUNCTION[geom.name](geom, scale))
    return cells

def _cells(points, dim, scale, dim2func={}, **named):
    import spindex as sx
    
    if not dim2func:
        dim2func.update({0:sx.get_cell,
                         1:sx.get_cells_1d,
                         2:sx.get_cells_2d})
    try:
        func = dim2func[dim]
    except KeyError:
        raise ValueError('dim must be 0, 1, or 2')
    return func(points, scale=scale, **named)

_TAG_TO_FUNCTION = {'MultiGeometry': _spdx_mg,
                    'Polygon'      : _spdx_pg,
                    'LineString'   : _spdx_ls,
                    'Point'        : _spdx_pt}
