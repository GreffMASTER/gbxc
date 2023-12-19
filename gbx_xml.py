import os
import xml.etree.ElementTree as ET
from datatypes import data_types
from gbxclasses import GBXClasses
import utils
import pathlib
import logging
from gbxerrors import ValidationError


REQUIRED_ATTRIB_LIST: list = ['version', 'unknown', 'class']
gbx_classes = GBXClasses()
node_counter = utils.Counter()
reference_table: ET.Element
body: ET.Element
gbx: ET.ElementTree
file_path_x: pathlib.Path


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
        if tag.tag == 'node':
            logging.error(f'XML Error: a head <chunk> cannot contain any <node>s!\n'
                          f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}")')
            raise ValidationError
        if tag.tag not in data_types:
            logging.error(f'XML Error: unknown data type tag <{tag.tag}>!\n'
                          f'(tag no. {i}, class "{class_id}", chunk "{chunk_id}")')
            raise ValidationError


def _validate_ref_table_entry(entry: ET.Element):
    if entry.tag == 'file':
        if 'flags' not in entry.attrib:
            logging.error('XML Error: missing required "flags" attribute in <file>!')
            raise ValidationError
        flags = entry.get('flags')
        name = ''
        if flags == '1':
            if 'name' not in entry.attrib:
                logging.error(f'XML Error: missing required "name" attribute in <file> tag! (uses flags "{flags})"')
                raise ValidationError
            name = entry.get('name')
        if flags == '5':
            if 'resindex' not in entry.attrib:
                logging.error(f'XML Error: missing required "resindex" attribute in <file> tag! (uses flags "{flags}"')
                raise ValidationError
            name = f'Resource {entry.get("resindex")}'
        if 'usefile' not in entry.attrib:
            logging.error(f'XML Error: missing required "usefile" attribute in <file> "{name}"')
            raise ValidationError
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
                logging.error(f'In {name}')
                raise ValidationError
    else:
        logging.error(f'XML Error: unknown <{entry.tag}> tag in reference table!')
        raise ValidationError


def _validate_node(node: ET.Element):
    logging.info(f'Validating <{node.tag} {node.attrib}>')
    global reference_table
    global body
    node_counter.increment()
    changed = False

    if 'link' in node.attrib:
        full_path = pathlib.Path(node.get('link'))
        link_dir = full_path.parent
        if len(link_dir.parents) > 0:
            os.chdir(link_dir)
            changed = True
        file_name = full_path.name
        try:
            f = open(file_name, 'r')
            f.close()
        except IOError:
            logging.error(f'XML Error: Linking error! File "{node.get("link")}" does not exist!')
            raise ValidationError
        try:
            link_xml = ET.parse(file_name)
        except ET.ParseError as e:
            logging.error(f'XML Error: Linking error! In file "{full_path}"!')
            logging.error(e.msg)
            raise ValidationError
        try:
            validate_gbx_xml(link_xml, str(file_name))
        except ValidationError:
            logging.error(f'XML Error: Linking error! In file "{full_path }"!')
            raise ValidationError
        except RecursionError:
            logging.error(f'XML Error: Infinite recursion detected! In file "{full_path }"!')
            raise ValidationError
        if changed:
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


def _validate_chunk_element(element: ET.Element):
    if element.tag == 'chunk':
        logging.error('XML Error: <chunk> tag cannot contain <chunk> child tags!')
        raise ValidationError

    if element.tag == 'node':
        try:
            _validate_node(element)
        except ValidationError:
            raise ValidationError
    elif element.tag == 'list':
        i = 0
        logging.info(f'Validating <list>')
        for element in element:
            i += 1
            if element.tag != 'element':
                logging.error('XML Error: <list> must only contain <element> child tags!')
                raise ValidationError
            for sub_element in element:
                if sub_element.tag == 'chunk':
                    logging.error(f'XML Error: <element> tag cannot contain <chunk> child tags!'
                                  f'In <element> no {i}')
                    raise ValidationError
                try:
                    _validate_chunk_element(sub_element)
                except ValidationError:
                    raise ValidationError
        logging.info('<list> valid')
    elif element.tag == 'switch':
        pass
    else:
        if element.tag not in data_types:
            logging.error(f'XML Error: unknown tag <{element.tag}>!')
            raise ValidationError


def _validate_chunk(chunk: ET.Element):
    logging.info(f'Validating <{chunk.tag} {chunk.attrib}>')
    if 'class' not in chunk.attrib:
        logging.error('XML Error: missing required "class" attribute in <chunk> tag!')
        raise ValidationError

    class_id = chunk.get('class')
    if 'id' not in chunk.attrib:
        logging.error('XML Error: missing required "id" attribute in <chunk> tag!')
        raise ValidationError

    chunk_id = chunk.get('id')
    if class_id[0] == 'C':  # Is a named class
        if class_id not in gbx_classes.get_dict():
            logging.error(f'XML Error: "class" attribute ("{class_id}") not found in GBX class dictionary!'
                          f'Please use hex value instead.')
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
            logging.error(f'In <chunk> class "{class_id}", id "{chunk_id}"')
            raise ValidationError
    logging.info('<chunk> valid')


def validate_gbx_xml(gbx_xml: ET.ElementTree, file_path: str):
    """
    Validates the GBX XML file. If an error occurred, 1 is returned.
    Otherwise, returns 0.

    :param gbx_xml:
    :param file_path:
    :return:
    """
    logging.info(f'Validating XML file "{file_path}"')
    global reference_table
    global body
    global gbx
    global file_path_x
    file_path_x = pathlib.Path(file_path)
    gbx = gbx_xml

    gbx_tag = gbx_xml.getroot()
    if gbx_tag and gbx_tag.tag != 'gbx':
        logging.error('XML Error: the xml file does not contain the <gbx> root tag!')
        raise ValidationError

    for req_attrib in REQUIRED_ATTRIB_LIST:
        if req_attrib not in gbx_tag.attrib:
            logging.error(f'XML Error: missing required "{req_attrib}" attribute in <gbx> tag!')
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
            logging.error('XML Error: missing required "ancestor" attribute in <reference_table>!')
            raise ValidationError

    # Validate head data
    if head_tag:
        i = 0
        for chunk in head_tag:
            i += 1
            try:
                _validate_head_chunk(chunk)
            except ValidationError:
                logging.error(f'Error in chunk no. {i} in <head>')
                raise ValidationError

    # Validate reference table
    if ref_tag:
        i = 0
        for entry in ref_tag:
            i += 1
            try:
                _validate_ref_table_entry(entry)
            except ValidationError:
                logging.error(f'Error in entry no. {i} in <reference_table>')
                raise ValidationError
        reference_table = ref_tag

    # Validate body
    body = body_tag
    i = 0
    for chunk in body_tag:
        i += 1
        if chunk.tag != 'chunk':
            logging.error(f'XML Error: <body> tag must only contain <chunk> child tags! (element no. {i})'
                          f'In <body>')
            raise ValidationError

        try:
            _validate_chunk(chunk)
        except ValidationError:
            logging.error(f'In <chunk> no. {i} in <body>')
            raise ValidationError

    logging.info('XML Validation passed!')
