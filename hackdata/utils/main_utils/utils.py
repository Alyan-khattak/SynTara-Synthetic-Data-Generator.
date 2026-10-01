# ═══════════════════════════════════════════════════════════════════
# utils.py — file I/O helpers: dill, numpy, yaml, json, ensure_dir
# ═══════════════════════════════════════════════════════════════════
# NS parity: mirrors Network Security save_object / load_object pattern.
# IMP: dill.dump(obj, file_obj) — object first, then file handle (NS convention).
###==============================================================
import json
import os
import sys

import dill
import numpy as np
import yaml

from hackdata.constants import export as export_const
from hackdata.exception.exception import HackDataException
from hackdata.logging.logger import logging


def ensure_dir(path: str) -> str:
    """Create the directory (and parents) if it does not exist.

    Parameters
    ----------
    path : str
        Directory path to create.

    Returns
    -------
    str
        The same path, so callers can inline: ``open(ensure_dir(p), ...)``.
    """
    try:
        os.makedirs(path, exist_ok=True)
        return path
    except Exception as e:
        raise HackDataException(e, sys)


def save_object(file_path: str, obj: object) -> None:
    """Serialise any Python object to disk using dill.

    Parameters
    ----------
    file_path : str
        Destination file path; parent directories are created automatically.
    obj : object
        Any picklable (dill-able) Python object.

    # DRY RUN: save_object("Artifacts/temp/run1/model.pkl", fitted_model)
    #   → os.makedirs("Artifacts/temp/run1/", exist_ok=True)
    #   → open file in "wb" mode
    #   → dill.dump(fitted_model, file_obj)  ← object first (NS rule)
    """
    try:
        logging.info(f"save_object: writing to {file_path}")
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, "wb") as file_obj:
            # IMP: argument order is dill.dump(obj, file) — NOT (file, obj)
            dill.dump(obj, file_obj)
        logging.info(f"save_object: done — {file_path}")
    except Exception as e:
        raise HackDataException(e, sys)


def load_object(file_path: str) -> object:
    """Deserialise a dill-pickled object from disk.

    Parameters
    ----------
    file_path : str
        Path to the dill file.

    Returns
    -------
    object
        The deserialised Python object.
    """
    try:
        logging.info(f"load_object: reading {file_path}")
        with open(file_path, "rb") as file_obj:
            obj = dill.load(file_obj)
        logging.info(f"load_object: done — {file_path}")
        return obj
    except Exception as e:
        raise HackDataException(e, sys)


def save_numpy_array_data(file_path: str, array: np.ndarray) -> None:
    """Save a NumPy array to disk in .npy format.

    Parameters
    ----------
    file_path : str
        Destination path (typically ending in .npy).
    array : np.ndarray
        The array to persist.
    """
    try:
        logging.info(f"save_numpy_array_data: writing to {file_path}")
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, "wb") as file_obj:
            np.save(file_obj, array)
        logging.info(f"save_numpy_array_data: done — {file_path}")
    except Exception as e:
        raise HackDataException(e, sys)


def load_numpy_array(file_path: str) -> np.ndarray:
    """Load a NumPy array from a .npy file.

    Parameters
    ----------
    file_path : str
        Path to the .npy file.

    Returns
    -------
    np.ndarray
        The loaded array.
    """
    try:
        logging.info(f"load_numpy_array: reading {file_path}")
        with open(file_path, "rb") as file_obj:
            array = np.load(file_obj)
        logging.info(f"load_numpy_array: done — {file_path}")
        return array
    except Exception as e:
        raise HackDataException(e, sys)


def read_yaml_file(file_path: str) -> dict:
    """Read a YAML file and return its contents as a dict.

    Parameters
    ----------
    file_path : str
        Path to the YAML file.

    Returns
    -------
    dict
        Parsed YAML content.
    """
    try:
        logging.info(f"read_yaml_file: reading {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
        logging.info(f"read_yaml_file: done — {file_path}")
        return content
    except Exception as e:
        raise HackDataException(e, sys)


def write_yaml_file(file_path: str, content: object, replace: bool = False) -> None:
    """Write content to a YAML file.

    Parameters
    ----------
    file_path : str
        Destination file path.
    content : object
        Any YAML-serialisable Python object.
    replace : bool
        When False (default) raise FileExistsError if the file already exists.
    """
    try:
        logging.info(f"write_yaml_file: writing to {file_path} (replace={replace})")
        if not replace and os.path.exists(file_path):
            raise FileExistsError(f"File already exists: {file_path}")
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(content, f, allow_unicode=True, default_flow_style=False)
        logging.info(f"write_yaml_file: done — {file_path}")
    except Exception as e:
        raise HackDataException(e, sys)


def read_json_file(file_path: str) -> dict:
    """Read a JSON file and return its contents as a dict.

    Parameters
    ----------
    file_path : str
        Path to the JSON file.

    Returns
    -------
    dict
        Parsed JSON content.
    """
    try:
        logging.info(f"read_json_file: reading {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        logging.info(f"read_json_file: done — {file_path}")
        return content
    except Exception as e:
        raise HackDataException(e, sys)


def write_json_file(file_path: str, content: object) -> None:
    """Write content to a JSON file with a stable indent.

    Parameters
    ----------
    file_path : str
        Destination file path; parent directories are created automatically.
    content : object
        Any JSON-serialisable Python object.
    """
    try:
        logging.info(f"write_json_file: writing to {file_path}")
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=export_const.EXP_JSON_INDENT, ensure_ascii=False)
        logging.info(f"write_json_file: done — {file_path}")
    except Exception as e:
        raise HackDataException(e, sys)

def cleanup_temp_runs(max_runs: int = None) -> None:
    """Delete old temp runs keeping only the most recent `max_runs`."""
    import shutil
    from hackdata.constants import paths as paths_const
    try:
        temp_dir = paths_const.ARTIFACTS_TEMP_DIR
        max_runs = max_runs or paths_const.TEMP_RUNS_MAX
        if not os.path.exists(temp_dir):
            return
        runs = [os.path.join(temp_dir, d) for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
        runs.sort(key=os.path.getmtime, reverse=True)
        for run in runs[max_runs:]:
            try:
                shutil.rmtree(run)
                logging.info(f"cleanup_temp_runs: deleted {run}")
            except Exception as err:
                logging.info(f"cleanup_temp_runs: could not delete {run}: {err}")
    except Exception as e:
        logging.info(f"cleanup_temp_runs: failed: {e}")
