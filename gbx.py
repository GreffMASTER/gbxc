import io
import logging
import os
import pathlib
import struct
from struct import pack
import xml.etree.ElementTree as ET
from typing import BinaryIO
from pathlib import Path

import datatypes
import gbx_xml
import utils
from datatypes import data_types, reset_lookback
from gbxerrors import GBXWriteError
from gbxclasses import GBXClasses


gbx_classes = GBXClasses()
gbx_file: BinaryIO
node_counter = utils.Counter()
directory_counter = utils.Counter()
node_pool = utils.GlobalNodePool()

# Globals
gbx_reftable: ET.Element
gbx_body: ET.Element
file_path_xml: pathlib.Path
version = 6


def write_list_head(chunk_data: BinaryIO, lst: ET.Element):
    count = 0
    for _element in lst:
        count += 1

    count_type_attrib = lst.get('count_type')
    if not count_type_attrib:
        if count > 4294967295:
            logging.error(f'Error: list count exceeded uint32 size!')
            raise GBXWriteError
        chunk_data.write(pack('<I', count))  # write number of elements
    else:
        if count_type_attrib != 'none':
            count_type = '<I'
            if count_type_attrib == 'uint32':
                count_type = '<I'
                if count > 4294967295:
                    logging.error(f'Error: list count exceeded uint32 size!')
                    raise GBXWriteError
            if count_type_attrib == 'uint16':
                count_type = '<H'
                if count > 65535:
                    logging.error(f'Error: list count exceeded uint16 size!')
                    raise GBXWriteError
            if count_type_attrib == 'uint8':
                count_type = '<B'
                if count > 255:
                    logging.error(f'Error: list count exceeded uint8 size!')
                    raise GBXWriteError
            chunk_data.write(pack(count_type, count))  # write number of elements
    # write list data
    for element in lst:
        for data_type in element:
            # custom data types
            if data_type.tag == 'list':
                write_list_head(chunk_data, data_type)
            else:  # regular data types
                try:
                    data_types[data_type.tag](chunk_data, data_type.text, data_type.attrib, data_type)
                except GBXWriteError:
                    logging.error(f'Error @ line {element.get("_line_num")}')
                    raise GBXWriteError
                except KeyError:
                    logging.error(f'Invalid data type <{data_type.tag}> for user data <list>!')
                    logging.error(f'Error @ line {element.get("_line_num")}')
                    raise GBXWriteError


def write_head_data(gbx_head: ET.Element) -> int:
    head_data = io.BytesIO()
    collapsed_chunk_data = io.BytesIO()
    head_data.write(pack('<I', len(gbx_head)))  # Number of chunks in head
    i = 0
    for head_chunk in gbx_head:  # For each chunk in head
        i += 1
        reset_lookback()
        chunk_data = io.BytesIO()  # Current chunk data
        class_id = head_chunk.get('class')
        chunk_id = head_chunk.get('id')
        if class_id[0] == 'C':  # named class
            full_class_id = f'{gbx_classes.get_dict().get(class_id)[:-3]}{chunk_id}'
            head_data.write(pack('<I', int(full_class_id, 16)))
        else:  # not a named class
            full_class_id = f'{class_id[:-3]}{chunk_id}'
            head_data.write(pack('<I', int(full_class_id, 16)))

        j = 0
        for data_type in head_chunk:  # For each element in chunk
            j += 1
            if data_type.tag == 'list':
                try:
                    write_list_head(chunk_data, data_type)
                except GBXWriteError:
                    logging.error(f'In chunk no. {i}, class "{class_id}", data tag no. {j}')
                    raise GBXWriteError
            else:
                try:
                    data_types[data_type.tag](chunk_data, data_type.text, data_type.attrib, data_type)
                except GBXWriteError:
                    logging.error(f'In chunk no. {i}, class "{class_id}", data tag no. {j}')
                    raise GBXWriteError

        chunk_data.seek(0)
        chunk_data_bytes = chunk_data.read()  # Get chunk data in bytes
        chunk_data.close()
        if 'skippable' in head_chunk.attrib:
            head_data.write(pack('<I', len(chunk_data_bytes) | 0x80000000))
        else:
            head_data.write(pack('<I', len(chunk_data_bytes)))
        collapsed_chunk_data.write(chunk_data_bytes)

    collapsed_chunk_data.seek(0)
    collapsed_chunk_data_bytes = collapsed_chunk_data.read()  # Get entire chunk data
    collapsed_chunk_data.close()

    head_data.write(collapsed_chunk_data_bytes)
    head_data.seek(0)
    head_data_bytes = head_data.read()  # Get entire chunk data and chunk head info
    head_data.close()

    gbx_file.write(pack('<I', len(head_data_bytes)))  # Write head size
    gbx_file.write(head_data_bytes)  # Write head data
    return 0


def write_dir(ref_tab_data: io.BytesIO, ref_file_data: io.BytesIO, direct: ET.Element):
    for element in direct:
        if element.tag == 'dir':
            directory_counter.increment()
            element.set('dir_id', str(directory_counter))
            ref_tab_data.write(pack('<I', len(element.get('name'))))
            ref_tab_data.write(bytes(element.get('name'), 'utf-8'))
            sub_dirs = 0
            for el in element:
                if el.tag == 'dir':
                    sub_dirs += 1
            ref_tab_data.write(pack('<I', sub_dirs))
            write_dir(ref_tab_data, ref_file_data, element)


def set_file_nodes(direct: ET.Element, dir_id):
    for element in direct:
        if element.tag == 'dir':
            set_file_nodes(element, element.get('dir_id'))
        elif element.tag == 'file':
            element.attrib['dirindex'] = dir_id


def write_ref_table() -> bytes:
    global gbx_reftable
    global version
    filecount = 0
    ref_tab_data = io.BytesIO()
    directory_counter.set_value(0)
    for file in gbx_reftable.iter('file'):  # Get used file count
        if 'nodeid' in file.attrib:
            filecount += 1
    ref_tab_data.write(pack('<I', filecount))  # write ex node count

    if filecount == 0:  # No files
        ref_tab_data.seek(0)
        out = ref_tab_data.read()
        ref_tab_data.close()
        return out

    ref_file_data = io.BytesIO()
    ref_tab_data.write(pack('<I', int(gbx_reftable.get('ancestor'))))  # Write ancestor level

    sub_dirs = 0
    for element in gbx_reftable:
        if element.tag == 'dir':
            sub_dirs += 1
    ref_tab_data.write(pack('<I', sub_dirs))

    write_dir(ref_tab_data, ref_file_data, gbx_reftable)  # Write all directories
    set_file_nodes(gbx_reftable, '0')

    files = []
    for file in gbx_reftable.iter('file'):
        if 'nodeid' in file.attrib:
            files.append(file)
    files.sort(key=lambda x: int(x.get('nodeid')))  # write the files in order as they are used in the body

    for file in files:
        flags = 1
        if file.get('resindex'):
            flags = 5
        ref_file_data.write(pack('<I', flags))
        if flags & 4 == 0:
            ref_file_data.write(pack('<I', len(file.get('name'))))
            ref_file_data.write(bytes(file.get('name'), 'utf-8'))
        else:
            ref_file_data.write(pack('<I', int(file.get('resindex'))))

        ref_file_data.write(pack('<I', int(file.get('nodeid'))))
        if version >= 5:
            ref_file_data.write(pack('<I', int(file.get('usefile'))))

        if flags & 4 == 0:
            ref_file_data.write(pack('<I', int(file.get('dirindex'))))

    ref_file_data.seek(0)
    ref_tab_data.write(ref_file_data.read())
    ref_file_data.close()
    ref_tab_data.seek(0)
    ref_tab_data_bytes = ref_tab_data.read()
    ref_tab_data.close()
    return ref_tab_data_bytes


def set_nodeid_to_node(in_ref_id: str, is_fid: bool = False) -> int:
    """ This function goes through every <file> in the <reference_table>
    and sets the correct node id if file with a given reference id exists.
    Alternatively, it tries to get previously used nodes in the body"""
    global gbx_reftable
    if gbx_reftable:
        for file in gbx_reftable.iter('file'):
            if file.get('refname') == in_ref_id:
                if 'nodeid' in file.attrib:
                    return int(file.get('nodeid'))
                else:
                    node_counter.increment()
                    file.attrib['nodeid'] = str(node_counter)
                    if not file.get('usefile'):
                        file.attrib['usefile'] = '0'
                        # if not specified, set default value to 0 (compatibility with older xmls that don't use fids)
                    if is_fid:
                        file.attrib['usefile'] = '1'
                    node_pool.addNode(file, int(node_counter))
                    return int(node_counter)
    # Not an external reference, try local node pool
    node_id = node_pool.getNodeIndexByRefName(in_ref_id)
    if node_id:
        return node_id
    else:
        raise GBXWriteError


def set_fid_to_file(in_ref_id: str) -> int:
    """ This function goes through every <file> in the <reference_table>
    and sets the correct fid id if file with a given reference id exists """
    if gbx_reftable:
        for file in gbx_reftable.iter('file'):
            if file.get('refname') == in_ref_id:
                if 'nodeid' in file.attrib:
                    return int(file.get('nodeid'))
                else:
                    node_counter.increment()
                    file.attrib['nodeid'] = str(node_counter)
                    node_pool.addNode(file, int(node_counter))
                    file.attrib['usefile'] = '1'
                    return int(node_counter)
    # Fids can only use external references
    raise GBXWriteError


def write_node(body_data: BinaryIO, xml_node: ET.Element):
    changed = 0  # Directory level

    node_ref_id = xml_node.get('ref')
    link_ref = xml_node.get('link')
    headless = xml_node.get('headless')
    custom = xml_node.get('custom')

    if custom:  # hacks, hacks, hacks
        class_id = xml_node.get('class')
        node_counter.increment()
        node_pool.addNode(xml_node, node_counter.get_value())
        xml_node.attrib['nodeid'] = str(node_counter)
        # Write node ref id
        body_data.write(pack('<I', int(node_counter)))

        if class_id[0] == 'C':  # every class name starts with a 'C'
            body_data.write(pack('<I', int(gbx_classes.get_dict().get(class_id), 16)))
        else:  # otherwise it's a hex value
            body_data.write(pack('<I', int(class_id, 16)))

        write_chunk(body_data, xml_node, True)
        return

    if node_ref_id:  # Node reference
        try:
            res = set_nodeid_to_node(node_ref_id)
            body_data.write(pack('<I', res))
        except GBXWriteError:
            logging.error(f'Error: failed to find node of id "{node_ref_id}"!')
            raise GBXWriteError
    elif link_ref:  # Uses a separate file (link)
        # Relative file stuff
        full_path = pathlib.Path(xml_node.get('link'))
        link_dir = full_path.parent
        for i in range(len(link_dir.parents)):
            changed += 1
        if len(link_dir.parents) > 0:
            os.chdir(link_dir)
        file_name = full_path.name

        link_gbx_res = gbx_xml.ParseXml(file_name)
        link_gbx = link_gbx_res[0]
        if not link_gbx:
            logging.error(f'Parsing failed for writing (somehow): {link_gbx_res[1]}')
            raise GBXWriteError

        link_body = link_gbx.findall('body')[0]
        class_id = link_gbx.getroot().get('class')

        node_counter.increment()
        node_pool.addNode(xml_node, node_counter.get_value())
        xml_node.attrib['nodeid'] = str(node_counter)
        body_data.write(pack('<I', int(node_counter)))

        # Write class id
        if class_id[0] == 'C':  # Every class name starts with a 'C' (ex. CPlugTree)
            body_data.write(pack('<I', int(gbx_classes.get_dict().get(class_id), 16)))
        else:                   # Use hex value instead
            body_data.write(pack('<I', int(class_id, 16)))

        # Write chunks
        for chunk in link_body:
            try:
                write_chunk(body_data, chunk)
            except GBXWriteError:
                logging.error(f'In file \"{file_name}\"')
                raise
        # Write terminator
        body_data.write(pack('<I', 0xFACADE01))
        # Go back to previous folder(s)
        for i in range(changed):
            os.chdir('..')
    else:  # not a reference, not a link, just normal node in gbx
        class_id = xml_node.get('class')
        if headless or class_id:
            if class_id:
                node_counter.increment()
                node_pool.addNode(xml_node, node_counter.get_value())
                # Set node ref id to be able to reference it
                xml_node.attrib['nodeid'] = str(node_counter)
                # Write node ref id
                body_data.write(pack('<I', int(node_counter)))
                # Write class id
                if class_id[0] == 'C':  # every class name starts with a 'C'
                    body_data.write(pack('<I', int(gbx_classes.get_dict().get(class_id), 16)))
                else:  # otherwise it's a hex value
                    body_data.write(pack('<I', int(class_id, 16)))
            # Write chunks
            for chunk in xml_node:
                try:
                    write_chunk(body_data, chunk)
                except GBXWriteError:
                    raise
            # Write terminator
            body_data.write(pack('<I', 0xFACADE01))
        else:  # No class, not headless. empty node
            body_data.write(pack('<I', 0xFFFFFFFF))


def write_fid(body_data: BinaryIO, xml_node: ET.Element):
    node_ref_id = xml_node.get('ref')
    if not node_ref_id:
        body_data.write(pack('<I', 0xFFFFFFFF))
        return

    try:
        res = set_fid_to_file(node_ref_id)
        body_data.write(pack('<I', res))
    except GBXWriteError:
        logging.error(f'Error: failed to find file of id "{node_ref_id}"!')
        raise GBXWriteError


def write_list(body_data: BinaryIO, lst: ET.Element):
    count = 0
    for _element in lst:
        count += 1

    count_type_attrib = lst.get('count_type')
    if not count_type_attrib:
        if count > 4294967295:
            logging.error(f'Error: list count exceeded uint32 size!')
            raise GBXWriteError
        body_data.write(pack('<I', count))  # write number of elements
    else:
        if count_type_attrib != 'none':
            count_type = '<I'
            if count_type_attrib == 'uint32':
                count_type = '<I'
                if count > 4294967295:
                    logging.error(f'Error: list count exceeded uint32 size!')
                    raise GBXWriteError
            if count_type_attrib == 'uint16':
                count_type = '<H'
                if count > 65535:
                    logging.error(f'Error: list count exceeded uint16 size!')
                    raise GBXWriteError
            if count_type_attrib == 'uint8':
                count_type = '<B'
                if count > 255:
                    logging.error(f'Error: list count exceeded uint8 size!')
                    raise GBXWriteError
            body_data.write(pack(count_type, count))  # write number of elements
    for element in lst:
        for c_element in element:
            try:
                write_chunk_element(body_data, c_element)
            except GBXWriteError:
                logging.error(f'Error @ line {element.get("_line_num")}')
                raise GBXWriteError


def write_chunk_element(body_data, element):
    # "Special" elements
    if element.tag == 'node' or element.tag == 'nod':
        try:
            write_node(body_data, element)
        except GBXWriteError:
            raise GBXWriteError
    elif element.tag == 'fid':
        try:
            write_fid(body_data, element)
        except GBXWriteError:
            raise GBXWriteError
    elif element.tag == 'list':
        try:
            write_list(body_data, element)
        except GBXWriteError:
            raise GBXWriteError
    elif element.tag == 'chunk':
        try:
            write_chunk(body_data, element)
        except GBXWriteError:
            raise GBXWriteError
    # Regular value tags (uint32, str, etc.)
    else:
        try:
            data_types[element.tag](body_data, element.text, element.attrib, element)
        except GBXWriteError:
            raise


def write_chunk(body_data: BinaryIO, chunk, custom = False):
    global gbx_reftable

    chunk_bin = io.BytesIO()

    class_id = chunk.get('class')
    chunk_id = chunk.get('id')
    link_ref = chunk.get('link')

    if not custom:
        if class_id[0] == 'C':  # named class
            full_class_id = f'{gbx_classes.get_dict().get(class_id)[:-3]}{chunk_id}'
            body_data.write(pack('<I', int(full_class_id, 16)))
        else:  # not a named class
            full_class_id = f'{class_id[:-3]}{chunk_id}'
            body_data.write(pack('<I', int(full_class_id, 16)))

    for i, data_type in enumerate(chunk):  # Iterate over chunks
        try:
            write_chunk_element(chunk_bin, data_type)
        except GBXWriteError:
            logging.error(f'In chunk no. {i}, class "{class_id}"')
            logging.error(f'Error @ line {data_type.get("_line_num")}')
            raise GBXWriteError

    chunk_bin.seek(0)
    chunk_bytes = chunk_bin.read()

    if chunk.get('skip'):
        chunk_size = len(chunk_bytes)
        body_data.write(b'PIKS')
        body_data.write(struct.pack('<I', chunk_size))

    body_data.write(chunk_bytes)


def write_body_data() -> bytes:
    reset_lookback()
    node_counter.set_value(0)

    body_data = io.BytesIO()
    for chunk in gbx_body:
        try:
            write_chunk(body_data, chunk)
        except GBXWriteError:
            raise GBXWriteError

    body_data.write(pack('<I', 0xFACADE01))  # End of body (end of file)
    node_counter.increment()
    body_data.seek(0)
    body_data_bytes = body_data.read()
    body_data.close()
    return body_data_bytes


def xml_to_gbx(xml_path: str, path: str, gbx: ET.Element):
    logging.info(f'Compiling file "{path}"...')
    global gbx_file
    global gbx_reftable
    global gbx_body
    global file_path_xml
    global version

    file_path_xml = pathlib.Path(xml_path)

    # Create missing directories in output path
    try:
        os.makedirs(os.path.dirname(path))
    except IOError:
        pass

    if 'complvl' in gbx.attrib:
        comp_lvl = int(gbx.get('complvl'))
        gbx_classes.set_comp_lvl(comp_lvl)

    if 'encoding' in gbx.attrib:
        utils.encoding = gbx.get('encoding')

    gbx_file = io.BytesIO()  # Make a file buffer before writing to file
    gbx_file.write(b'GBX')
    version = int(gbx.get('version'))
    gbx_file.write(pack('<H', version))
    gbx_file.write(b'BUU')
    if version >= 4:
        gbx_file.write(bytes(gbx.get('unknown'), 'utf-8'))

    class_id = gbx.get('class')
    if class_id[0] == 'C':
        gbx_file.write(pack('<i', int(gbx_classes.get_dict().get(class_id), 16)))
    else:
        gbx_file.write(pack('<i', int(class_id, 16)))

    og_dir = os.path.abspath(os.getcwd())
    os.chdir(file_path_xml.parent)

    # Write head
    if int(gbx.get('version')) <= 5:
        datatypes.lookback.version = 2
    if int(gbx.get('version')) >= 6:
        head_tag = gbx.find('head')
        if head_tag:
            try:
                write_head_data(head_tag)
            except GBXWriteError:
                raise GBXWriteError
        else:
            gbx_file.write(pack('<I', 0))  # Head size = 0

    gbx_body = gbx.find('body')
    gbx_reftable = gbx.find('reference_table')

    try:
        body_data = write_body_data()
    except GBXWriteError:
        logging.error(f'In file \"{xml_path}\"')
        raise GBXWriteError

    if gbx_reftable:
        reftable_data = write_ref_table()
        if not reftable_data:
            return 1
        gbx_file.write(pack('<I', int(node_counter)))
        gbx_file.write(reftable_data)
    else:  # No ex nodes
        gbx_file.write(pack('<I', int(node_counter)))
        gbx_file.write(pack('<I', 0))

    gbx_file.write(body_data)

    gbx_file.seek(0, 0)
    gbx_data = gbx_file.read()

    # No issues, ready to write to file

    os.chdir(og_dir)
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    out_file = open(path, 'wb', 0)
    out_file.write(gbx_data)
    out_file.close()

    return 0
