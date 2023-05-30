import io
import logging
import os
import pathlib
from struct import pack
import xml.etree.ElementTree as ET
from typing import BinaryIO

import utils
from datatypes import data_types, reset_lookback
from gbxerrors import GBXWriteError
from gbxclasses import GBXClasses


gbx_classes = GBXClasses()
gbx_file: BinaryIO
node_counter = utils.Counter()
directory_counter = utils.Counter()

# Globals
gbx_reftable: ET.Element
gbx_body: ET.Element
file_path_x: pathlib.Path
path_history: list = []
link_recursion: int = 0


def write_head_data(gbx_head: ET.Element) -> int:
    head_data = io.BytesIO()
    collapsed_chunk_data = io.BytesIO()
    head_data.write(pack('<I', len(gbx_head)))  # Number of chunks in head
    i = 0
    for head_chunk in gbx_head:  # For each chunk in head
        i += 1
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
            try:
                data_types[data_type.tag](chunk_data, data_type.text, data_type.attrib)
            except GBXWriteError:
                print(f'In chunk no. {i}, class "{class_id}", data tag no. {j}')
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
            ref_tab_data.write(pack('<I', len(element.get('name'))))
            ref_tab_data.write(bytes(element.get('name'), 'utf-8'))
            sub_dirs = 0
            for el in element:
                if el.tag == 'dir':
                    sub_dirs += 1
            ref_tab_data.write(pack('<I', sub_dirs))
            write_dir(ref_tab_data, ref_file_data, element)
        elif element.tag == 'file':
            element.attrib['dirindex'] = str(directory_counter)


def write_ref_table() -> bytes:
    global gbx_reftable
    filecount = 0
    ref_tab_data = io.BytesIO()
    directory_counter.set_value(0)
    for file in gbx_reftable.iter('file'):  # Get used file count
        if 'nodeid' in file.attrib:
            filecount += 1
    ref_tab_data.write(pack('<I', filecount))

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

    files = []
    for file in gbx_reftable.iter('file'):
        if 'nodeid' in file.attrib:
            files.append(file)
    files.sort(key=lambda x: int(x.get('nodeid')))

    for file in files:
        flags = int(file.get('flags'))
        ref_file_data.write(pack('<I', flags))
        if flags & 4 == 0:
            ref_file_data.write(pack('<I', len(file.get('name'))))
            ref_file_data.write(bytes(file.get('name'), 'utf-8'))
        else:
            ref_file_data.write(pack('<I', int(file.get('resindex'))))

        ref_file_data.write(pack('<I', int(file.get('nodeid'))))
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


def set_nodeid_to_node(ref_id: str) -> int:
    global gbx_reftable
    for file in gbx_reftable.iter('file'):
        if file.get('refname') == ref_id:
            if 'nodeid' in file.attrib:
                return int(file.get('nodeid'))
            else:
                node_counter.increment()
                file.attrib['nodeid'] = str(node_counter)
                return int(node_counter)

    for node in gbx_body.iter('node'):
        refname = node.get('refname')
        if refname and refname == ref_id:
            if 'nodeid' in node.attrib:
                return int(node.get('nodeid'))
    raise GBXWriteError


def write_node(body_data: BinaryIO, xml_node: ET.Element):
    global file_path_x
    global path_history
    global link_recursion

    node_ref_id = xml_node.get('ref')
    link_ref = xml_node.get('link')
    if node_ref_id:
        try:
            res = set_nodeid_to_node(node_ref_id)
            body_data.write(pack('<I', res))
        except GBXWriteError:
            print(f'Error: failed to find node of id "{node_ref_id}"!')
            raise GBXWriteError
    elif link_ref:
        path_history.insert(link_recursion, file_path_x)
        link_recursion += 1
        file_path_x = file_path_x.parents[0].joinpath(xml_node.get('link'))
        link_gbx = ET.parse(file_path_x)
        link_body = link_gbx.findall('body')[0]

        class_id = link_gbx.getroot().get('class')
        node_counter.increment()
        link_body.attrib['nodeid'] = str(node_counter)
        body_data.write(pack('<I', int(node_counter)))
        if class_id[0] == 'C':
            body_data.write(pack('<I', int(gbx_classes.get_dict().get(class_id), 16)))
        else:
            body_data.write(pack('<I', int(class_id, 16)))
        for chunk in link_body:
            try:
                write_chunk(body_data, chunk)
            except GBXWriteError:
                raise GBXWriteError
        body_data.write(pack('<I', 0xFACADE01))
        link_recursion -= 1
        file_path_x = path_history[link_recursion]
    else:
        class_id = xml_node.get('class')
        if class_id:
            node_counter.increment()
            xml_node.attrib['nodeid'] = str(node_counter)
            if 'idless' not in xml_node.attrib:
                body_data.write(pack('<I', int(node_counter)))

            if class_id[0] == 'C':
                body_data.write(pack('<I', int(gbx_classes.get_dict().get(class_id), 16)))
            else:
                body_data.write(pack('<I', int(class_id, 16)))

            for chunk in xml_node:
                try:
                    write_chunk(body_data, chunk)
                except GBXWriteError:
                    raise GBXWriteError
            body_data.write(pack('<I', 0xFACADE01))
        else:
            body_data.write(pack('<I', 0xFFFFFFFF))


def write_list(body_data: BinaryIO, lst):
    count = 0
    for _element in lst:
        count += 1
    body_data.write(pack('<I', count))  # write number of elements
    for element in lst:
        for c_element in element:
            try:
                write_chunk_element(body_data, c_element)
            except GBXWriteError:
                raise GBXWriteError


def write_chunk_element(body_data, element):
    if element.tag == 'node':
        try:
            write_node(body_data, element)
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
    else:
        try:
            data_types[element.tag](body_data, element.text, element.attrib, element)
        except GBXWriteError:
            raise GBXWriteError


def write_chunk(body_data: BinaryIO, chunk):
    global gbx_reftable
    class_id = chunk.get('class')
    chunk_id = chunk.get('id')
    if class_id[0] == 'C':  # named class
        full_class_id = f'{gbx_classes.get_dict().get(class_id)[:-3]}{chunk_id}'
        body_data.write(pack('<I', int(full_class_id, 16)))
    else:  # not a named class
        full_class_id = f'{class_id[:-3]}{chunk_id}'
        body_data.write(pack('<I', int(full_class_id, 16)))

    i = 0
    for data_type in chunk:  # Iterate over chunks
        i += 1
        try:
            write_chunk_element(body_data, data_type)
        except GBXWriteError:
            print(f'In chunk no. {i}, class "{class_id}"')
            raise GBXWriteError


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
    global file_path_x

    file_path_x = pathlib.Path(xml_path)

    # Create missing directories in output path
    try:
        os.makedirs(os.path.dirname(path))
    except IOError:
        pass

    if 'complvl' in gbx.attrib:
        comp_lvl = int(gbx.get('complvl'))
        gbx_classes.set_comp_lvl(comp_lvl)

    gbx_file = open(path, 'wb', 0)
    gbx_file.write(b'GBX')
    gbx_file.write(pack('<H', int(gbx.get('version'))))
    gbx_file.write(b'BUU')
    gbx_file.write(bytes(gbx.get('unknown'), 'utf-8'))

    class_id = gbx.get('class')
    if class_id[0] == 'C':
        gbx_file.write(pack('<i', int(gbx_classes.get_dict().get(class_id), 16)))
    else:
        gbx_file.write(pack('<i', int(class_id, 16)))

    # Write head
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

    gbx_file.close()
    return 0
