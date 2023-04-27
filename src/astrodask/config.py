import importlib
import os
from typing import Dict, List, Optional

import yaml

_conf = dict()


def get_config(reload: bool = False) -> dict:
    global _conf
    prefix = "ASTRODASK_"
    envconf = {
        k.replace(prefix, "").lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }
    path = envconf.pop("config_path", None)
    if path is None:
        path = os.path.join(os.path.expanduser("~"), ".astrodask.yaml")
    if not reload and len(_conf) > 0:
        return _conf
    config = get_config_fromfile(path)
    config.update(**envconf)
    _conf = config
    return config


def get_config_fromfile(resource: str) -> Dict:
    """
    Load config from a YAML file.
    Parameters
    ----------
    resource
        The name of the resource or file path.

    Returns
    -------

    """
    if resource == "":
        raise ValueError("Config name cannot be empty.")
    # order (in descending order of priority):
    # 1. absolute path?
    path = os.path.expanduser(resource)
    if os.path.isabs(path):
        with open(path, "r") as file:
            conf = yaml.safe_load(file)
        return conf
    bpath = os.path.expanduser("~/.config/astrodask")
    path = os.path.join(bpath, resource)
    # 2. non-absolute path?
    # 2.1. check ~/.config/astrodask/units/
    if os.path.isfile(path):
        with open(path, "r") as file:
            conf = yaml.safe_load(file)
        return conf
    # 2.2 check astrodask package resource units/
    resource_path = "astrodask.configfiles"
    resource_elements = resource.split("/")
    rname = resource_elements[-1]
    if len(resource_elements) > 1:
        resource_path += "." + ".".join(resource_elements[:-1])
    with importlib.resources.path(resource_path, rname) as fp:
        with open(fp, "r") as file:
            conf = yaml.safe_load(file)
    return conf


def merge_dicts_recursively(
    dict_a: Dict, dict_b: Dict, path: Optional[List] = None
) -> Dict:
    """
    Merge two dictionaries recursively.
    Parameters
    ----------
    dict_a
        The first dictionary.
    dict_b
        The second dictionary.
    path
        The path to the current node.

    Returns
    -------
    dict
    """
    if path is None:
        path = []
    for key in dict_b:
        if key in dict_a:
            if isinstance(dict_a[key], dict) and isinstance(dict_b[key], dict):
                merge_dicts_recursively(dict_a[key], dict_b[key], path + [str(key)])
            elif dict_a[key] == dict_b[key]:
                pass  # same leaf value
            else:
                raise Exception("Conflict at %s" % ".".join(path + [str(key)]))
        else:
            dict_a[key] = dict_b[key]
    return dict_a


def get_config_fromfiles(paths: List[str], subconf_keys: Optional[List[str]] = None):
    """
    Load and merge multiple YAML config files
    Parameters
    ----------
    paths
        Paths to the config files.
    subconf_keys
        The keys to the correct sub configuration within each config.

    Returns
    -------

    """
    confs = []
    for path in paths:
        confs.append(get_config_fromfile(path))
    conf = {}
    for confdict in confs:
        conf = merge_dicts_recursively(conf, confdict)
    return conf


_config = get_config()
