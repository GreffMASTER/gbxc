import xml.etree.ElementTree as ET
from datatypes import data_types
from gbxclasses import GBXClasses
import utils
import pathlib


REQUIRED_ATTRIB_LIST: list = ['version', 'unknown', 'class']
gbx_classes = GBXClasses()
node_counter = utils.Counter()
reference_table: ET.Element
body: ET.Element
gbx: ET.ElementTree
file_path_x: pathlib.Path


def _validate_class_id(class_id: str) -> int:
    if len(class_id) != 8:  # Class id must be 4 bytes (8 hex characters)
        print(f'XML Error: "class" attribute ("{class_id}") must be 8 characters long!')
        return 1

    try:
        int(class_id, 16)
    except ValueError:
        print(f'XML Error: "class" attribute ("{class_id}") has incorrect hex value!')
        return 1

    return 0


def _validate_chunk_id(chunk_id: str) -> int:
    if len(chunk_id) != 3:  # Class id must be 4 bytes (8 hex characters)
        print(f'XML Error: "id" attribute ("{chunk_id}") must be 3 characters long!')
        return 1

    try:
        int(chunk_id, 16)
    except ValueError:
        print(f'XML Error: "id" attribute ("{chunk_id}") has incorrect hex value!')
        return 1

    return 0


def _validate_head_chunk(chunk: ET.Element) -> int:
    if chunk.tag != 'chunk':
        print('XML Error: <head> tag must only contain <chunk> tags!')
        return 1

    if 'class' not in chunk.attrib:
        print('XML Error: missing required "class" attribute in <chunk> tag!')
        return 1
    class_id = chunk.get('class')

    if 'id' not in chunk.attrib:
        print('XML Error: missing required "id" attribute in <chunk> tag!')
        return 1
    chunk_id = chunk.get('id')

    if class_id[0] == 'C':      # Is a named class
        if class_id not in gbx_classes.get_dict():
            print(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!')
            print('Please use hex value instead.')
            return 1
    else:                       # Not a named class (hex value)
        if _validate_class_id(class_id) == 1:
            return 1
    if _validate_chunk_id(chunk_id) == 1:
        return 1

    i = 0
    for tag in chunk:
        i += 1
        if tag.tag == 'node':
            print(f'XML Error: a head <chunk> cannot contain any <node>s!'
                  f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}")')
            return 1
        if tag.tag not in data_types:
            print(f'XML Error: unknown data type tag <{tag.tag}>!'
                  f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}")')
            return 1


def _validate_ref_table_entry(entry: ET.Element) -> int:
    if entry.tag == 'file':
        if 'flags' not in entry.attrib:
            print('XML Error: missing required "flags" attribute in <file>!')
            return 1
        flags = entry.get('flags')
        name = ''
        if flags == '1':
            if 'name' not in entry.attrib:
                print(f'XML Error: missing required "name" attribute in <file> tag! (uses flags "{flags})"')
                return 1
            name = entry.get('name')
        if flags == '5':
            if 'resindex' not in entry.attrib:
                print(f'XML Error: missing required "resindex" attribute in <file> tag! (uses flags "{flags}"')
                return 1
            name = f'Resource {entry.get("resindex")}'
        if 'usefile' not in entry.attrib:
            print(f'XML Error: missing required "usefile" attribute in <file> "{name}"')
            return 1
        if 'refname' not in entry.attrib:
            print(f'XML Error: missing required "refname" attribute in <file> "{name}"')
            return 1
    elif entry.tag == 'dir':
        if 'name' not in entry.attrib:
            print(f'XML Error: missing required "name" attribute in <dir> tag!')
            return 1
        for directory in entry:
            res = _validate_ref_table_entry(directory)
            if res == 1:
                name = entry.get('name')
                print(f'In {name}')
                return 1
    else:
        print(f'XML Error: unknown <{entry.tag}> tag in reference table!')
        return 1

    return 0


def _validate_node(node: ET.Element) -> int:
    global reference_table
    global body
    node_counter.increment()

    if 'link' in node.attrib:
        # TODO node linking (eg. <node link="Node.Solid.Xml"/>)
        # replaces the <node/> tag with a new <node> tag with class
        # of the body of the linked xml file
        # needs reference table update (ancestor level and stuff)

        link_path = file_path_x.parents[0].joinpath(node.get('link'))
        if not link_path.exists():
            print(f'XML Error: Linking error! File "{link_path}"does not exist!')
            return 1

        link_xml = ET.parse(link_path)
        if validate_gbx_xml(link_xml, str(link_path)) > 0:
            print(f'XML Error: Linking error! In file "{link_path}"!')
            return 1
        '''

        link_class = link_xml.getroot().get('class')
        print(link_class)
        link_reference_table = link_xml.findall('reference_table')[0]
        for i in link_reference_table.getchildren():
            reference_table.append(link_reference_table)
        reference_table.append(link_reference_table.getchildren())
        for i in reference_table.iter():
            print(i)

        print(link_reference_table)
        link_body = link_xml.findall('body')[0]
        link_body.tag = 'node'
        link_node = ET.Element('node')
        link_node.attrib['class'] = link_class
        link_node.append(link_body)
        return 0
        '''
        return 0

    if 'class' in node.attrib:
        # Validate class id
        class_id = node.get('class')
        if class_id[0] == 'C':  # Is a named class
            if class_id not in gbx_classes.get_dict():
                print(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!')
                print('Please use hex value instead.')
                return 1
        else:  # Not a named class (hex value)
            if _validate_class_id(class_id) == 1:
                return 1

        # Validate chunks inside the node
        i = 0
        for chunk in node:
            i += 1
            if chunk.tag != 'chunk':
                print(f'XML Error: <node> tag must only contain <chunk> child tags!')
                print(f'In <node> no. {i} "{class_id}"')
                return 1
            if _validate_chunk(chunk) == 1:
                print(f'In <node> no. {i} "{class_id}"')
                return 1
        return 0
    return 0


def _validate_chunk(chunk: ET.Element) -> int:
    if 'class' not in chunk.attrib:
        print('XML Error: missing required "class" attribute in <chunk> tag!')
        return 1

    class_id = chunk.get('class')
    if 'id' not in chunk.attrib:
        print('XML Error: missing required "id" attribute in <chunk> tag!')
        return 1

    chunk_id = chunk.get('id')
    if class_id[0] == 'C':  # Is a named class
        if class_id not in gbx_classes.get_dict():
            print(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!')
            print('Please use hex value instead.')
            return 1
    else:  # Not a named class (hex value)
        if _validate_class_id(class_id) == 1:
            return 1
    if _validate_chunk_id(chunk_id) == 1:
        return 1

    # Validate chunk elements
    i = 0
    for tag in chunk:
        i += 1
        if tag.tag == 'chunk':
            print('XML Error: <chunk> tag cannot contain <chunk> child tags!')
            print(f'In <chunk> class "{class_id}", id "{chunk_id}"')
            return 1

        if tag.tag == 'node':
            if _validate_node(tag) == 1:
                print(f'In <chunk> class "{class_id}", id "{chunk_id}"')
                return 1
        elif tag.tag == 'list':
            for element in tag:
                if element.tag != 'element':
                    print('XML Error: <list> must only contain <element> child tags!')
                    print(f'In <chunk> class "{class_id}", id "{chunk_id}"')
                    return 1
                for sub_element in element:
                    if sub_element.tag == 'chunk':
                        print('XML Error: <element> tag cannot contain <chunk> child tags!')
                        print(f'In <chunk> class "{class_id}", id "{chunk_id}"')
                        return 1
        else:
            if tag.tag not in data_types:
                print(f'XML Error: unknown data type tag <{tag.tag}>! (tag no. {i}, class "{class_id}")')
                return 1

    return 0


def validate_gbx_xml(gbx_xml: ET.ElementTree, file_path: str) -> int:
    """
    Validates the GBX XML file. If an error occurred, 1 is returned.
    Otherwise, returns 0.

    :param gbx_xml:
    :param file_path:
    :return:
    """
    global reference_table
    global body
    global gbx
    global file_path_x
    file_path_x = pathlib.Path(file_path)
    gbx = gbx_xml

    gbx_tag = gbx_xml.getroot()
    if gbx_tag and gbx_tag.tag != 'gbx':
        print('XML Error: the xml file does not contain the <gbx> root tag!')
        return 1

    for req_attrib in REQUIRED_ATTRIB_LIST:
        if req_attrib not in gbx_tag.attrib:
            print(f'XML Error: missing required {req_attrib} attribute in <gbx> tag!')
            return 1

    # Check if "gbx" tag has one and only one "body" tag
    i = 0
    body_tag = None
    for tag in gbx_tag.iter('body'):
        body_tag = tag
        i += 1
    if i != 1:
        print('XML Error: <gbx> tag must have one and only one <body> child tag!')
        return 1

    # Check if "gbx" tag has only one "head" tag
    i = 0
    head_tag = None
    for tag in gbx_tag.iter('head'):
        head_tag = tag
        i += 1
    if i > 1:
        print('XML Error: <gbx> tag must have only one <head> child tag!')
        return 1

    # Check if "gbx" tag has only one "reference_table" tag
    i = 0
    ref_tag = None
    for tag in gbx_tag.iter('reference_table'):
        ref_tag = tag
        i += 1
    if i > 1:
        print('XML Error: <gbx> tag must have only one <reference_table> child tag!')
        return 1

    # If it has a reference table, validate it as well
    if ref_tag:
        if 'ancestor' not in ref_tag.attrib:
            print('XML Error: missing required "ancestor" attribute in <reference_table>!')
            return 1

    # Validate head data
    if head_tag:
        i = 0
        for chunk in head_tag:
            i += 1
            if _validate_head_chunk(chunk) == 1:
                print(f'Error in chunk no. {i} in <head>')
                return 1

    # Validate reference table
    if ref_tag:
        i = 0
        for entry in ref_tag:
            i += 1
            res = _validate_ref_table_entry(entry)
            if res == 1:
                print(f'Error in entry no. {i} in <reference_table>')
                return 1
        reference_table = ref_tag

    # Validate body
    body = body_tag
    i = 0
    for chunk in body_tag:
        i += 1
        if chunk.tag != 'chunk':
            print(f'XML Error: <body> tag must only contain <chunk> child tags! (element no. {i})')
            print('In <body>')
            return 1

        res = _validate_chunk(chunk)
        if res == 1:
            print(f'In <chunk> no. {i} in <body>')
            return 1

    return 0
