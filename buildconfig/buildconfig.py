# [ ] load .buildconfig.json.sh
# [ ] check root: True

from __future__ import print_function

__all__ = ['BuildCommand', 'BuildTarget', 'BuildConfig']

import sys
import os
import json
import hashlib
import fnmatch
import re
import collections
import pipes
import shlex
import yaml



class SchemaDict(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self.store = {}
        self.update(dict(*args, **kwargs))

    def __getitem__(self, key):
        if not key in self.store:
            schema = self.schema
            if key in schema:
                if isinstance(schema[key], dict):
                    self.store[key] = {}
                elif isinstance(schema[key], list):
                    self.store[key] = []
                elif isinstance(schema[key], SchemaDict):
                    self.store[key] = schema[key]()
                else:
                    return None
        return self.store[key]

    def _verify_schema(self, key, typeclass, value):
        if isinstance(typeclass, list):
            if len(typeclass) != 1:
                raise ValueError('schema error of %r, lists must have only one element but is %r' % (type(self).__name__, value))
            if not isinstance(value, list):
                value = [ value ]
                # raise ValueError('key %r must be a list for %r but is %r' % (key, type(self).__name__, value))
            return [ self._verify_schema(key, typeclass[0], i) for i in value ]
        elif isinstance(typeclass, dict):
            if len(typeclass.keys()) != 1:
                raise ValueError('schema error of %r, dicts must have only one element but is %r' % (type(self).__name__), value)
            if not isinstance(value, dict):
                raise ValueError('key %r must be a dict for %r but is %r' % (key, type(self).__name__, value))
            return dict([ (self._verify_schema(key, list(typeclass.keys())[0], k), self._verify_schema(key, list(typeclass.values())[0], v)) for (k, v) in value.items() ])
        elif isinstance(value, typeclass):
            return value
        elif hasattr(typeclass, 'from_dict') and isinstance(value, dict):
            return typeclass.from_dict(value)
        elif typeclass == str and isinstance(value, float):
            return str(value)
        elif typeclass == str and isinstance(value, bool):
            return str(value)
        elif typeclass == str and isinstance(value, int):
            return str(value)
        elif typeclass == str and isinstance(value, basestring): # py3?
            return str(value)
        else:
            raise ValueError('key %r must be a %r for %r but is %r' % (key, typeclass, type(self).__name__, value))

    def __setitem__(self, key, value):
        if not key.startswith('_'):
            schema = self.schema
            if not key in schema:
                raise ValueError('key %r not in schema of %r' % (key, type(self).__name__))
            typeclass = schema[key]
            value = self._verify_schema(key, typeclass, value)
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __repr__(self):
        return repr(self.store)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(str(e))

    @classmethod
    def from_dict(cls, src):
        return cls(src)

    def to_dict(self):
        def _convert(i):
            if isinstance(i, SchemaDict) or isinstance(i, dict):
                return dict([ (_convert(k), _convert(v)) for (k, v) in i.items() ])
            elif isinstance(i, list):
                return list([ _convert(v) for v in i ])
            else:
                return i
        return _convert(self)

    @classmethod
    def merge(cls, *items):
        def _merge(target, source):
            if isinstance(target, dict) or isinstance(target, SchemaDict):
                for k in source.keys():
                    if k in target and (isinstance(source[k], dict) or isinstance(source[k], list)):
                        _merge(target[k], source[k])
                    else:
                        target[k] = source[k]
            elif isinstance(target, list):
                target.append(source)
            else:
                raise ValueError('unexpected %r <- %r' % (type(target), type(source)))
        res = cls()
        for i in items:
            _merge(res, i)
        return res

    @classmethod
    def json_default(cls, obj):
        if isinstance(obj, SchemaDict):
            res = dict(obj)
            res['.class'] = type(obj).__name__
            return res
        return obj

    @classmethod
    def json_object_hook(cls, obj):
        if isinstance(obj, dict) and '.class' in obj:
            cls = globals()[obj['.class']]
            del obj['.class']
            return cls(obj)
        return obj







# replace curly bracket substitutions
# {somevalue} -> callback(somevalue)
# {somevalue {someothervalue}} -> callback('somevalue '+callback('someothervalue'))
# {{} => {, {}} => }
def curly_subst(string, callback):
    res = ''
    while True:
        n = string.find('{')
        if n == -1:
            res += string
            string = ''
            break
        res += string[0:n]
        string = string[n:]
        if string.startswith('{{}'):
            res += '{'
            string = string[3:]
        elif string.startswith('{}}'):
            res += '}'
            string = string[3:]
        else:
            l = 1
            p = 1
            while l > 0 and p < len(string):
                if string[p:].startswith('{{}'):
                    p += 2
                elif string[p:].startswith('{}}'):
                    p += 2
                if string[p] == '{':
                    l += 1
                elif string[p] == '}':
                    l -= 1
                p += 1
            macro = string[0:p]
            string = string[p:]
            macro = macro[1:][:-1]
            tmp1 = curly_subst(macro, callback)
            tmp2 = callback(tmp1)
            res += tmp2
    return res











class BuildCommand(SchemaDict):
    schema = {
        'persistent': bool,
        'restart': bool,
        'only_platform': str,
        'env': { str: str },
        'params': { str: str },
        'cwd': str,
        'shell': str,
        'cmd': [ str ],
    }

    def __init__(self, *args, **kwargs):
        if isinstance(args[0], dict) and 'cmd' in args[0] and isinstance(args[0]['cmd'], str):
            args[0]['cmd'] = shlex.split(args[0]['cmd'])
        super(BuildCommand, self).__init__(*args, **kwargs)
        if self.shell and self.cmd: raise ValueError('cannot set shell and cmd')
        if self.restart and not self.persistent: raise ValueError('cannot set restart without persistent')

    def _get_params(self):
        params = dict(self._target._config.params)
        params.update(self._target.params)
        params.update(self.params)
        return params

    def _subst(self, val):
        if isinstance(val, list):
            return [ self._subst(i) for i in val ]
        if isinstance(val, dict):
            return dict([ (self._subst(k), self._subst(v)) for (k, v) in val.items() ])
        params = self._get_params()

        def port_from_path(path):
            return 2000 + int(hashlib.md5(path.encode('utf-8')).hexdigest()[-8], 16) % 30000

        def repl(string):
            if string in params:
                return params[string]
            if string.startswith('port:'):
                parts = string.split(':')
                if len(parts) != 2:
                    raise ValueError('port: need one argumnet')
                return str(port_from_path(parts[1]))
            if string.startswith('relpath:'):
                parts = string.split(':')
                if len(parts) != 3:
                    raise ValueError('relpath: needs two arguments')
                if not parts[2].endswith('/'):
                    parts[2] += '/'
                if not parts[1].startswith(parts[2]):
                    raise ValueError('relpath: first argument must start with second argument')
                return parts[1][len(parts[2]):]
            raise ValueError('unknown substitution: ' + repr(string))

        return curly_subst(val, repl)

    def get_params(self):
        res = self._target._config.params
        res.update(self._target.params)
        res.update(self.params)
        return self._subst(res)

    def get_env(self):
        res = self._target._config.env
        res.update(self._target.env)
        res.update(self.env)
        return self._subst(res)

    def get_cwd(self):
        if not self.cwd:
            return self._get_params().get('config_dir', '.')
        return self._subst(self.cwd)

    def get_shell(self):
        return self._subst(self.shell)

    def get_cmd(self):
        return self._subst(self.cmd)

    def is_shell(self):
        return self.shell is not None

    def get_persistent_id(self):
        res = self._target.params['config_dir']+' '+self._target.name
        res = re.sub('[^a-zA-Z]+', '-', res)[1:]
        return res




class BuildTarget(SchemaDict):
    schema = {
        'files': str,
        'env': { str: str },
        'params': { str: str },
        'depends': [ str ],
        'commands': [ BuildCommand ]
    }

    def __init__(self, *args, **kwargs):
        # implicit command creation
        if len(args) == 1 and isinstance(args[0], dict):
            tmp_target = {}
            tmp_command = {}
            for (k, v) in args[0].items():
                if k in self.schema:
                    tmp_target[k] = v
                else:
                    tmp_command[k] = v
            if tmp_command:
                if 'commands' in tmp_target:
                    raise ValueError('cannot directly specify a command and also use the commands array')
                super(BuildTarget, self).__init__(tmp_target)
                self.commands.append(BuildCommand(tmp_command))
                return
        super(BuildTarget, self).__init__(*args, **kwargs)

    def get_commands(self):
        res = []
        for depend in self.depends:
            res += self._config.get_target_by_name(depend).get_commands()
        for command in self.commands:
            if command.only_platform and command.only_platform != sys.platform:
                continue
            res.append(command)
        return res



class BuildConfig(SchemaDict):
    schema = {
        'root': bool,
        'env': { str: str },
        'params': { str: str },
        'targets': { str : BuildTarget }
    }

    def __init__(self, *args, **kwargs):
        super(BuildConfig, self).__init__(*args, **kwargs)
        for (name, target) in self.targets.items():
            target._config = self
            target.name = name
            for command in target.commands:
                command._target = target

    @classmethod
    def merge(cls, *items):
        res = super(BuildConfig, cls).merge(*items)
        for target in res.targets.values():
            target._config = res
        return res

    @classmethod
    def load_json(cls, path):
        with open(path, 'r') as fp:
            res = cls.from_dict(json.load(fp))
            for i in res.targets.values():
                i.params['config_file'] = os.path.abspath(path)
                i.params['config_dir'] = os.path.dirname(os.path.abspath(path))+'/'
            return res

    @classmethod
    def load_yml(cls, path):
        with open(path, 'r') as fp:
            res = cls.from_dict(yaml.load(fp))
            for i in res.targets.values():
                i.params['config_file'] = os.path.abspath(path)
                i.params['config_dir'] = os.path.dirname(os.path.abspath(path))+'/'
            return res

    @classmethod
    def load_at_path(cls, path):
        res = BuildConfig()
        while path != '/':
            config = None
            if config is None:
                name = os.path.join(path, '.buildconfig.json')
                if os.path.isfile(name):
                    config = BuildConfig.load_json(name)
            if config is None:
                name = os.path.join(path, '.buildconfig.yml')
                if os.path.isfile(name):
                    config = BuildConfig.load_yml(name)
            if config:
                res = BuildConfig.merge(res, config)
                if config.root:
                    break
            path = os.path.dirname(path)
        return res

    def get_targets_for_file(self, file):
        res = []
        for target in self.targets.values():
            if not target.files:
                pass
            elif fnmatch.fnmatch(file, target.files):
                res.append(target)
            elif fnmatch.fnmatch(file[len(target.params['config_dir']):], target.files):
                res.append(target)
        return res

    def get_global_targets(self):
        res = []
        for target in self.targets.values():
            if not target.files:
                res.append(target)
        return res

    def get_target_by_name(self, name):
        for target in self.targets.values():
            if target.name == name:
                return target
        return None
