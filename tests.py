import os

from gbx import xml_to_gbx
import xml.etree.ElementTree as ET
from gbx_xml import validate_gbx_xml
from hashlib import md5

from gbxerrors import ValidationError, GBXWriteError


def checksum_file(path, exp_md5: str) -> bool:
    if not exp_md5:
        return False
    with open(path, 'rb') as fb:
        gbx_data = fb.read()
        new_md5 = md5(gbx_data).digest().hex()
    if new_md5 == exp_md5:
        print('\nMD5 Checksum: OK')
        return True
    else:
        print(f'\nMD5 Checksum: FAIL, expected checksum is incorrect!\n'
              f'Expected "{exp_md5}", got "{new_md5}".')
        return False


def do_file(xml_path: str, gbx_path: str, do_checksum: bool) -> bool:
    og_path = os.getcwd()
    try:
        gbx_tree = ET.parse(xml_path)
    except ET.ParseError as e:
        print(f'\nFailed to parse XML file! ({e.code}, {e.position})')
        os.chdir(og_path)
        return False
    try:
        validate_gbx_xml(gbx_tree, xml_path)
    except ValidationError:
        print('\nGBX XML parsing failed!')
        os.chdir(og_path)
        return False
    try:
        xml_to_gbx(xml_path, gbx_path, gbx_tree.getroot())
    except GBXWriteError:
        print(f'\nThere was an error while writing the "{gbx_path}" GBX file!')
        os.chdir(og_path)
        return False

    os.chdir(og_path)
    if do_checksum:
        assert checksum_file(gbx_path, gbx_tree.getroot().get('md5')) is True

    return True


def test_collection_tm1():
    assert do_file('Samples/TM1.0/GameData/Collections/Alpine.TMCollection.xml',
                   'Samples/TM1.0/GameData/Collections/Alpine.TMCollection.Gbx', True) is True


def test_script_tm1():
    assert do_file('Samples/TM1.0/GameData/Races/Script/DisplayCheckpointTime.Script.xml',
                   'Samples/TM1.0/GameData/Races/Script/DisplayCheckpointTime.Script.Gbx', True) is True


def test_resindex_tm1():
    assert do_file('Samples/TM1.0/Custom/Scene3d/RallyBase32x32.Scene3d.xml',
                   'Samples/TM1.0/Custom/Scene3d/RallyBase32x32.Scene3d.Gbx', True) is True


def test_frontier_tmo():
    assert do_file('Samples/TMO/TMEDFrontier/DesertToDesert2/DesertToDesert2.TMEDFrontier.xml',
                   'Samples/TMO/TMEDFrontier/DesertToDesert2/DesertToDesert2.TMEDFrontier.Gbx', True) is True


def test_slope_tmo():
    assert do_file('Samples/TMO/TMEDSlope/SpeedSlope/SpeedSlope.TMEDSlope.xml',
                   'Samples/TMO/TMEDSlope/SpeedSlope/SpeedSlope.TMEDSlope.Gbx', True) is True


def main():
    test_collection_tm1()
    test_collection_tm1()
    test_resindex_tm1()
    test_frontier_tmo()
    test_slope_tmo()


if __name__ == '__main__':
    main()
