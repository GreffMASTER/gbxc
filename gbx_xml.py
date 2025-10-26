import os
from datatypes import data_types
from gbxclasses import GBXClasses
import utils
import pathlib
import logging
from gbxerrors import ValidationError
import xml.etree.ElementTree as ET


REQUIRED_ATTRIB_LIST: list = ['version', 'unknown', 'class']
gbx_classes = GBXClasses()
node_counter = utils.Counter()
reference_table: ET.Element
body: ET.Element
gbx: ET.ElementTree
file_path_xml: pathlib.Path


class XmlLineReader:
    def __init__(self, xml_file) -> None:
        self._iter = iter(xml_file)
        self._current_line = -1

    @property
    def line(self):
        return self._current_line

    def read(self, *_):
        try:
            self._current_line += 1
            return next(self._iter)
        except:
            return None


def ParseXml(path: str) -> tuple[ET.ElementTree or None, str]:
    """
    Parses XML file and automatically assigns a line number to each element using "_line_num" attribute
    """
    gbx_tree: ET.ElementTree
    gbx_elem: ET.Element = None
    og_cwd = os.getcwd()
    gbx_io = XmlLineReader(open(path, 'r'))
    try:
        for _, elem in ET.iterparse(gbx_io, ['start']):
            elem: ET.Element
            elem.set('_line_num', str(gbx_io.line + 1))
            if gbx_elem is None:  # set first element to be the tree
                gbx_elem = elem
        gbx_tree = ET.ElementTree(gbx_elem)
    except ET.ParseError as e:
        logging.error(f'Failed to parse XML file! (code: {e.code}, pos: {e.position})')
        return None, f'Failed to parse XML file! (code: {e.code}, pos: {e.position})'
    os.chdir(og_cwd)
    return gbx_tree, ""


def _validate_class_id(class_id: str):
    if len(class_id) != 8:  # Class id must be 4 bytes (8 hex characters)
        logging.error(f'XML Error: "class" attribute ("{class_id}") must be 8 characters long!')
        raise ValidationError
    try:
        int(class_id, 16)
    except ValueError:
        logging.error(f'XML Error: "class" attribute ("{class_id}") has incorrect hex value!')
        raise ValidationError


def _validate_chunk_id(chunk_id: str):
    if len(chunk_id) != 3:  # Class id must be 4 bytes (8 hex characters)
        logging.error(f'XML Error: "id" attribute ("{chunk_id}") must be 3 characters long!')
        raise ValidationError
    try:
        int(chunk_id, 16)
    except ValueError:
        logging.error(f'XML Error: "id" attribute ("{chunk_id}") has incorrect hex value!')
        raise ValidationError


def _validate_head_chunk(chunk: ET.Element):
    logging.info('Validating head <chunk>')
    if chunk.tag != 'chunk':
        logging.error('XML Error: <head> tag must only contain <chunk> tags!')
        raise ValidationError
    if 'class' not in chunk.attrib:
        logging.error('XML Error: missing required "class" attribute in <chunk> tag!')
        raise ValidationError
    class_id = chunk.get('class')

    if 'id' not in chunk.attrib:
        logging.error('XML Error: missing required "id" attribute in <chunk> tag!')
        raise ValidationError
    chunk_id = chunk.get('id')

    if class_id[0] == 'C':      # Is a named class
        if class_id not in gbx_classes.get_dict():
            logging.error(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!\n'
                          'Please use hex value instead.')
            raise ValidationError
    else:                       # Not a named class (hex value)
        try:
            _validate_class_id(class_id)
        except ValidationError:
            raise ValidationError
    try:
        _validate_chunk_id(chunk_id)
    except ValidationError:
        raise ValidationError

    i = 0
    for tag in chunk:
        i += 1
        if tag.tag == 'node' or tag.tag == 'nod' or tag.tag == 'fid':
            logging.error(f'XML Error: a head <chunk> cannot contain any <node>s or <fid>s!\n'
                          f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}") @ line {tag.get("_line_num")}')
            raise ValidationError
        if tag.tag not in data_types:
            if tag.tag != 'list':  # HAXXXX
                logging.error(f'XML Error: unknown data type tag <{tag.tag}>!\n'
                              f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}") @ line {tag.get("_line_num")}')
                raise ValidationError


def _validate_ref_table_entry(entry: ET.Element):
    if entry.tag == 'file':
        # if 'flags' not in entry.attrib:
        #     logging.error('XML Error: missing required "flags" attribute in <file>!')
        #     raise ValidationError
        # flags = entry.get('flags')
        name = ''
        # if flags == '1':
        #     if 'name' not in entry.attrib:
        #         logging.error(f'XML Error: missing required "name" attribute in <file> tag! (uses flags "{flags})"')
        #        raise ValidationError
        #     name = entry.get('name')
        # if flags == '5':
        #     if 'resindex' not in entry.attrib:
        #         logging.error(f'XML Error: missing required "resindex" attribute in <file> tag! (uses flags "{flags}"')
        #         raise ValidationError
        #     name = f'Resource {entry.get("resindex")}'
        # if 'usefile' not in entry.attrib:
        #    logging.error(f'XML Error: missing required "usefile" attribute in <file> "{name}"')
        #    raise ValidationError
        if 'name' not in entry.attrib and 'resindex' not in entry.attrib:
            logging.error(f'XML Error: <file> must have either "name" or "resindex" attribute.')
            raise ValidationError
        if 'name' in entry.attrib and 'resindex' in entry.attrib:
            logging.error(f'XML Error: <file> must have either "name" or "resindex" attribute, not both.')
            raise ValidationError
        name = entry.get('name')
        if not name:
            name = f'Resource {entry.get("resindex")}'
        if 'refname' not in entry.attrib:
            logging.error(f'XML Error: missing required "refname" attribute in <file> "{name}"')
            raise ValidationError
    elif entry.tag == 'dir':
        if 'name' not in entry.attrib:
            logging.error(f'XML Error: missing required "name" attribute in <dir> tag!')
            raise ValidationError
        for directory in entry:
            try:
                _validate_ref_table_entry(directory)
            except ValidationError:
                name = entry.get('name')
                logging.error(f'In {name} @ line {directory.get("_line_num")}')
                raise ValidationError
    else:
        logging.error(f'XML Error: unknown <{entry.tag}> tag in reference table!')
        raise ValidationError


def _validate_node(node: ET.Element):
    logging.info(f'Validating <{node.tag} {node.attrib}>')
    global reference_table
    global body
    node_counter.increment()
    changed = 0

    if 'custom' in node.attrib:
        return  # hacks, hacks, hacks

    if 'link' in node.attrib:
        full_path = pathlib.Path(node.get('link'))
        link_dir = full_path.parent
        for i in range(len(link_dir.parents)):
            changed += 1

        if len(link_dir.parents) > 0:
            os.chdir(link_dir)

        file_name = full_path.name
        try:
            f = open(file_name, 'r')
            f.close()
        except IOError:
            logging.error(f'XML Error: Linking error! File "{node.get("link")}" does not exist!')
            raise ValidationError
        link_xml_res = ParseXml(file_name)
        link_xml = link_xml_res[0]
        if not link_xml:
            logging.error(f'XML Error: Linking error! In file "{full_path}"!')
            logging.error(link_xml_res[1])
            raise ValidationError
        # XML Parsed
        try:
            validate_gbx_xml(link_xml, str(file_name))
        except ValidationError:
            logging.error(f'XML Error: Linking error! In file "{full_path}"!')
            raise ValidationError
        except RecursionError:
            logging.error(f'XML Error: Infinite recursion detected! In file "{full_path}"!')
            raise ValidationError
        
        for i in range(changed):
            os.chdir('..')
        return
    if 'headless' not in node.attrib:
        if 'class' in node.attrib:
            # Validate class id
            class_id = node.get('class')
            if class_id[0] == 'C':  # Is a named class
                if class_id not in gbx_classes.get_dict():
                    logging.error(f'XML Error: "class" attribute ("{class_id}")'
                                  f'not found in GBX class dictionary!\n'
                                  f'Please use hex value instead.')
                    raise ValidationError
            else:  # Not a named class (hex value)
                try:
                    _validate_class_id(class_id)
                except ValidationError:
                    raise ValidationError

            # Validate chunks inside the node
            i = 0
            for chunk in node:
                i += 1
                if chunk.tag != 'chunk':
                    logging.error(f'XML Error: <node> tag must only contain <chunk> child tags!'
                                  f'In <node> no. {i} "{class_id}"')
                    raise ValidationError
                try:
                    _validate_chunk(chunk)
                except ValidationError:
                    logging.error(f'In <node> no. {i} "{class_id}"')
                    raise ValidationError
    else:
        # Validate chunks inside the node
        i = 0
        for chunk in node:
            i += 1
            if chunk.tag != 'chunk':
                logging.error(f'XML Error: <node> tag must only contain <chunk> child tags!'
                              f'In <node> no. {i}')
                raise ValidationError
            try:
                _validate_chunk(chunk)
            except ValidationError:
                logging.error(f'In <node> no. {i}')
                raise ValidationError
    logging.info('<node> valid')


def _validate_fid(fid: ET.Element):

    # if 'ref' not in fid.attrib:
    #    logging.error(f'XML Error: <fid> tag must have a "ref" attribute!')
    #    raise ValidationError
    logging.info('<fid> valid')


def _validate_chunk_element(element: ET.Element):
    if element.tag == 'chunk':
        logging.error('XML Error: <chunk> tag cannot contain <chunk> child tags!')
        raise ValidationError

    if element.tag == 'node' or element.tag == 'nod':
        try:
            _validate_node(element)
        except ValidationError:
            raise ValidationError
    elif element.tag == 'fid':
        try:
            _validate_fid(element)
        except ValidationError:
            raise ValidationError
    elif element.tag == 'list':
        i = 0
        logging.info(f'Validating <list>')
        for element in element:
            i += 1
            if element.tag != 'element':
                logging.error('XML Error: <list> must only contain <element> child tags!'
                              f'In <element> no {i} @ line {element.get("_line_num")}')
                raise ValidationError
            for sub_element in element:
                if sub_element.tag == 'chunk':
                    logging.error(f'XML Error: <element> tag cannot contain <chunk> child tags!'
                                  f'In <element> no {i} @ line {sub_element.get("_line_num")}')
                    raise ValidationError
                try:
                    _validate_chunk_element(sub_element)
                except ValidationError:
                    raise ValidationError
        logging.info('<list> valid')
    elif element.tag == 'switch':
        pass  # TODO implement validation for switches (what did they do again?)
    else:
        if element.tag not in data_types:
            logging.error(f'XML Error: unknown tag <{element.tag}>!'
                          f'@ line {element.get("_line_num")}')
            raise ValidationError


def _validate_chunk(chunk: ET.Element):
    logging.info(f'Validating <{chunk.tag} {chunk.attrib}>')
    if 'class' not in chunk.attrib:
        logging.error('XML Error: missing required "class" attribute in <chunk> tag!')
        raise ValidationError

    class_id = chunk.get('class')
    if 'id' not in chunk.attrib:
        logging.error(f'XML Error: missing required "id" attribute in <chunk> tag!'
                      f'@ line {chunk.get("_line_num")}')
        raise ValidationError

    chunk_id = chunk.get('id')
    if class_id[0] == 'C':  # Is a named class
        if class_id not in gbx_classes.get_dict():
            logging.error(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!'
                          f'Please use hex value instead. @ line {chunk.get("_line_num")}')
            raise ValidationError
    else:  # Not a named class (hex value)
        try:
            _validate_class_id(class_id)
        except ValidationError:
            raise ValidationError
    try:
        _validate_chunk_id(chunk_id)
    except ValidationError:
        raise ValidationError

    # Validate chunk elements
    for tag in chunk:
        try:
            _validate_chunk_element(tag)
        except ValidationError:
            logging.error(f'In <chunk> class "{class_id}", id "{chunk_id}"'
                          f'@ line {tag.get("_line_num")}')
            raise ValidationError
    logging.info('<chunk> valid')


def validate_gbx_xml(gbx_xml: ET.ElementTree, file_path: str):
    """
    Validates the GBX XML file. If an error occurred, 1 is returned.
    Otherwise, returns 0.

    :param gbx_xml: ET.ElementTree
    :param file_path: str
    :return:
    """
    logging.info(f'Validating XML file "{file_path}"')
    global reference_table
    global body
    global gbx
    global file_path_xml
    file_path_x = pathlib.Path(file_path)
    gbx = gbx_xml

    og_dir = os.getcwd()
    os.chdir(file_path_x.parent)

    gbx_tag = gbx_xml.getroot()
    if gbx_tag and gbx_tag.tag != 'gbx':
        logging.error('XML Error: the xml file does not contain the <gbx> root tag!')
        raise ValidationError

    for req_attrib in REQUIRED_ATTRIB_LIST:
        if req_attrib not in gbx_tag.attrib:
            logging.error(f'XML Error: missing required "{req_attrib}" attribute in <gbx> tag!\n'
                          f'In {file_path} @ line {gbx_tag.get("_line_num")}')
            raise ValidationError

    encoding = gbx_tag.get('encoding')
    if not encoding:
        logging.warning(f'XML Warning for \"{file_path}\": missing \"encoding\" attribute. Using \"ascii\" as default...')
    else:
        if encoding != 'ascii' and encoding != 'cp1251':
            logging.error(f'XML Error: \"encoding\" attribute can only be either \"ascii\" or \"cp1251\"')
            raise ValidationError

    # Check if "gbx" tag has one and only one "body" tag
    i = 0
    body_tag = None
    for tag in gbx_tag.iter('body'):
        body_tag = tag
        i += 1
    if i != 1:
        logging.error('XML Error: <gbx> tag must have one and only one <body> child tag!')
        raise ValidationError

    # Check if "gbx" tag has only one "head" tag
    i = 0
    head_tag = None
    for tag in gbx_tag.iter('head'):
        head_tag = tag
        i += 1
    if i > 1:
        logging.error('XML Error: <gbx> tag must have only one <head> child tag!')
        raise ValidationError

    # Check if "gbx" tag has only one "reference_table" tag
    i = 0
    ref_tag: ET.Element = None
    for tag in gbx_tag.iter('reference_table'):
        ref_tag = tag
    if i > 1:
        logging.error('XML Error: <gbx> tag must have only one <reference_table> child tag!')
        raise ValidationError

    # If it has a reference table, validate it as well
    if ref_tag:
        if 'ancestor' not in ref_tag.attrib:
            logging.error(f'XML Error: missing required "ancestor" attribute in <reference_table>!'
                          f'In {file_path} @ line {ref_tag.get("_line_num")}')
            raise ValidationError

    # Validate head data
    if head_tag:
        i = 0
        for chunk in head_tag:
            i += 1
            try:
                _validate_head_chunk(chunk)
            except ValidationError:
                logging.error(f'Error in chunk no. {i} in <head>'
                              f'In {file_path} @ line {chunk.get("_line_num")}')
                raise ValidationError

    # Validate reference table
    if ref_tag:
        i = 0
        for entry in ref_tag:
            i += 1
            try:
                _validate_ref_table_entry(entry)
            except ValidationError:
                logging.error(f'Error in entry no. {i} in <reference_table>'
                              f'In {file_path} @ line {entry.get("_line_num")}')
                raise ValidationError
        reference_table = ref_tag

    # Validate body
    body = body_tag
    i = 0
    for chunk in body_tag:
        i += 1
        if chunk.tag != 'chunk':
            logging.error(f'XML Error: <body> tag must only contain <chunk> child tags! (element no. {i})'
                          f'In {file_path} @ line {chunk.get("_line_num")}')
            raise ValidationError

        try:
            _validate_chunk(chunk)
        except ValidationError:
            logging.error(f'In {file_path} @ line {chunk.get("_line_num")}')
            raise ValidationError

    os.chdir(og_dir)
    logging.info('XML Validation passed!')
