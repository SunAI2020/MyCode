# -*- coding: utf-8 -*-
"""资产批量导入测试"""
from asset_importer import parse_csv, parse_tags


def test_parse_tags_dedup():
    assert parse_tags('web, db ,web; 财务') == ['web', 'db', '财务']


def test_parse_tags_empty():
    assert parse_tags('') == []
    assert parse_tags(None) == []


def test_parse_csv_basic():
    text = 'name,ip,type,importance\nweb01,10.0.0.1,SERVER,HIGH\n'
    assets, errors = parse_csv(text)
    assert len(assets) == 1
    assert assets[0]['name'] == 'web01'
    assert assets[0]['ip'] == '10.0.0.1'
    assert assets[0]['importance'] == 'HIGH'
    assert errors == []


def test_parse_csv_missing_field():
    text = 'name,ip\nweb01,10.0.0.1\nbroken\n'
    assets, errors = parse_csv(text)
    assert len(assets) == 1
    assert len(errors) == 1


def test_parse_csv_tags_normalized():
    text = 'name,ip,tags\nweb01,10.0.0.1,"web, 生产; db"\n'
    assets, errors = parse_csv(text)
    assert assets[0]['tags'] == 'web,生产,db'


def test_parse_csv_header_alias_chinese():
    text = '名称,IP地址,类型\nweb01,10.0.0.1,SERVER\n'
    assets, _ = parse_csv(text)
    assert assets[0]['name'] == 'web01'
    assert assets[0]['ip'] == '10.0.0.1'
