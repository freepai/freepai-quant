# -*- coding:utf-8 -*-

"""
Validator module.

Author: HuangTao
Date:   2018/03/21
Email:  huangtao@ifclover.com
"""

import json

from quant.utils import exceptions


def _field(data, field, required):
    if field:
        data = data or {}
        if not isinstance(data, dict):
            raise exceptions.ValidationError("field `{field}` lost".format(field=field))
        if required and field not in data:
            raise exceptions.ValidationError("field `{field}` lost".format(field=field))
        return data.get(field)
    else:
        return data


def bool_field(data, field=None, required=True):
    """ bool validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. If `field` value is "True" or "true", return True;
        2. If `field` value is "False" or "false", return False;
        3. If `field` is not exits and required is False, return None.

    Raise:
        ValidationError: The type of `field` is not bool.
    """
    field_data = _field(data, field, required)
    if str(field_data).lower() == "true":
        return True
    if str(field_data).lower() == "false":
        return False
    if not required:
        return None
    raise exceptions.ValidationError("The type of `{field}` is not bool".format(field=field or data))


def int_field(data, field=None, required=True):
    """ int validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. Int field.
        2. If `field` is not exits and required is False, return None.

    Raise:
        ValidationError: The type of `field` is not int.
    """
    field_data = _field(data, field, required)
    if not field_data and field_data != 0 and not required:
        return None
    try:
        return int(field_data)
    except:
        raise exceptions.ValidationError("The type of `{field}` is not int".format(field=field or data))


def float_field(data, field=None, required=True):
    """ float validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. Float field.
        2. If `field` is not exits and required is False, return None.

    Raise:
        ValidationError: The type of `field` is not float.
    """
    field_data = _field(data, field, required)
    if not field_data and not required:
        return None
    try:
        return float(field_data)
    except:
        raise exceptions.ValidationError("The type of `{field}` is not float".format(field=field or data))


def string_field(data, field=None, required=True):
    """ string validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. String field.
        2. If `field` is not exits and required is False, return None.
    """
    field_data = _field(data, field, required)
    if not field_data:
        return ""
    if not field_data and not required:
        return None
    return str(field_data)


def list_field(data, field=None, required=True):
    """ list validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. List field.
        2. If `field` is not exits and required is False, return None.

    Raise:
        ValidationError: The type of `field` is not list.
    """
    field_data = _field(data, field, required)
    if not field_data and not required:
        return None
    if isinstance(field_data, str):
        try:
            field_data = json.loads(field_data)
        except:
            raise exceptions.ValidationError("The type of `{field}` is not list".format(field=field or data))
    if not isinstance(field_data, (list, set, tuple)):
        raise exceptions.ValidationError("The type of `{field}` is not list".format(field=field or data))
    return list(field_data)


def dict_field(data, field=None, required=True):
    """ dict validator.

    Args:
        data: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        field: If `field` is None, `data` is `field`, otherwise get `field` from `data`.
        required: if `field` must in `data`, True or False, default is True.

    Returns:
        1. Dict field.
        2. If `field` is not exits and required is False, return None.

    Raise:
        ValidationError: The type of `field` is not dict.
    """
    field_data = _field(data, field, required)
    if not field_data and not required:
        return None
    if isinstance(field_data, str):
        try:
            field_data = json.loads(field_data)
        except:
            raise exceptions.ValidationError("The type of `{field}` is not dict".format(field=field or data))
    if not isinstance(field_data, dict):
        raise exceptions.ValidationError("The type of `{field}` is not dict".format(field=field or data))
    return field_data
