# https://www.sublimetext.com/docs/3/api_reference.html#sublime.View
# http://docs.sublimetext.info/en/latest/reference/commands.html

import sys
import os
import sublime
import sublime_plugin
import pipes
import subprocess
from .buildconfig import buildconfig
from .buildconfig import runpersistent

config_cache = None
config_cache_mtimes = {}
def load_config(view):
    global config_cache, config_cache_mtimes
    if config_cache:
        for (file, time) in config_cache_mtimes.items():
            try:
                if os.stat(file).st_mtime != time:
                    config_cache = None
                    break
            except:
                config_cache = None
    if config_cache:
        return config_cache
    try:
        config = buildconfig.BuildConfig.load_at_path(view.file_name())
    except Exception as e:
        view.show_popup('BuildConfig error: ' + str(e), max_width=500)
        raise
    config_cache_mtimes = dict([ (file, os.stat(file).st_mtime) for file in set([i.params['config_file'] for i in config.targets.values()]) ])
    config_cache = config
    return config


def perform_command(command, view):
    print(">", command)
    view.show_popup(repr(command))
    cmd = [command.get_shell()] if command.is_shell() else command.get_cmd()
    cwd = command.get_cwd()
    env = command.get_env()
    if command.persistent:
        if command.persistent:
            if command.restart:
                runpersistent.kill(command.get_persistent_id())
            runpersistent.open(
                command.get_persistent_id(),
                [command.shell] if command.is_shell() else cmd,
                shell=command.is_shell(),
                cwd=cwd,
                env=env
            )
    else:
        view.window().run_command('exec', {
            'cmd': cmd,
            'working_dir': cwd,
            'quiet': True,
            'shell': command.is_shell(),
            'env': env
        })
        # @TODO: wait for it??


last_target_by_file = {}
def perform_target(target, view):
    last_target_by_file[view.file_name()] = target.name
    target._config.params['file'] = view.file_name()
    for command in target.get_commands():
        perform_command(command, view)






class BuildconfigLastCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not self.view.file_name():
            return
        sublime.active_window().run_command('save_all')
        config = load_config(self.view)
        if not config:
            return
        if self.view.file_name() in last_target_by_file:
            target = config.get_target_by_name(last_target_by_file[self.view.file_name()])
            if target:
                perform_target(target, self.view)
                return
        self.view.run_command('build_config_run')

class BuildconfigRunCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not self.view.file_name():
            return
        sublime.active_window().run_command('save_all')
        config = load_config(self.view)
        if not config:
            return
        targets = config.get_targets_for_file(self.view.file_name()) + config.get_global_targets()
        if not targets:
            return
        options = [i.name for i in targets]
        def on_selection(index):
            if index == -1: return
            target = config.get_target_by_name(options[index])
            perform_target(target, self.view)
        if len(options) == 1 and config.get_target_by_name(options[0]).files:
            on_selection(0)
        else:
            self.view.window().show_quick_panel(options, on_selection)

