"""Normalize native advisory calls without executing tools or storing content."""
import importlib.util
from pathlib import Path
import shlex


def _load(path, name):
    if not path.is_file() or path.is_symlink():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def advise(base, skills, state, cwd, session, operation, command, event,
           agent=None, read_cwd=None, detectors=None):
    """Use verified native identity and literal command context; remain advisory."""
    try:
        if (base / '.disabled-mainframe-skill-reminder').exists():
            return None
        method = _load(base / 'skill_reminder.py', 'mainframe_reminder_method')
        detector = _load((detectors or base / 'detectors') / 'mainframe-skill-reminder.py', 'mainframe_reminder_detector')
        if method is None or detector is None:
            return None
        data = {'hook_event_name': event, 'session_id': session,
                'tool_use_id': operation, 'cwd': str(cwd),
                'tool_input': {'command': command}, 'tool_response': 'native read attempt'}
        if agent is not None:
            data['agent_id'] = agent
        return method.advisory(data, state, base, detector,
                               skill_roots=(skills,), read_cwd=read_cwd)
    except Exception:
        return None


def read_command(inputs, fields):
    """Convert only a literal native file read, never arbitrary tool input."""
    values = [inputs[k] for k in fields if k in inputs]
    if not values or any(v != values[0] for v in values):
        return None
    value = values[0]
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    return 'cat ' + shlex.quote(value)


def known_failed(response):
    """Use only structured native failure fields; never interpret raw stdout."""
    if not isinstance(response, dict):
        return False
    if response.get('isError') is True or response.get('is_error') is True or response.get('success') is False:
        return True
    return any(type(response.get(k)) is int and response[k] != 0
               for k in ('exit_code', 'exitCode'))
