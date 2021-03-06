# https://www.sublimetext.com/docs/3/api_reference.html#sublime.View
# http://docs.sublimetext.info/en/latest/reference/commands.html

import sys
import os
import sublime
import sublime_plugin
import subprocess
import threading
import traceback
from .buildconfig import buildconfig
from .buildconfig import runpersistent

try:
    if sys.platform != 'win32':
        os.environ["PATH"] += ':/usr/local/bin'
except:
    pass

busy = False
last_target_by_file = {}


def panel_erase():
    output = sublime.active_window().create_output_panel('buildconfig')
    output.run_command('erase_view')
    output.set_read_only(True)
    sublime.active_window().run_command('show_panel', {'panel': 'output.buildconfig'})

def panel_print(txt):
    output = sublime.active_window().find_output_panel('buildconfig')
    output.set_read_only(False)
    output.run_command('append', {'characters': str(txt), 'scroll_to_end': True})
    output.set_read_only(True)
    sublime.active_window().run_command('show_panel', {'panel': 'output.buildconfig'})


def load_config(path):
    try:
        config = buildconfig.BuildConfig.load_at_path(path)
    except Exception as e:
        raise
        print(e)
        tb = traceback.format_exc()
        print(tb)
        panel_erase()
        panel_print('[buildconfig config error] %s\n' % tb)
        return None
    return config



def perform_command(command):
    def pipestream(fp):
        def run():
            while True:
                line = fp.readline()
                if len(line) == 0:
                    break
                panel_print(line.decode('utf-8'))
        thread = threading.Thread(target=run)
        thread.start()
    panel_print('> ' + repr(command) + '\n')
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
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            shell=command.is_shell(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        pipestream(proc.stdout)
        pipestream(proc.stderr)
        ret = proc.wait()
        if ret != 0:
            panel_print('[ERROR] return code %d\n' % ret)
        else:
            panel_print('> success')



def perform_target(target, file):
    global busy, last_target_by_file
    busy = True
    try:
        last_target_by_file[file] = target.name
        panel_erase()
        panel_print("> %s\n" % target.name)
        target._config.params['file'] = file
        def run():
            try:
                for command in target.get_commands():
                    perform_command(command)
            except Exception as e:
                tb = traceback.format_exc()
                panel_print('[ERROR] %s\n' % tb)
            busy = False
        thread = threading.Thread(target=run)
        thread.start()
    finally:
        busy = False






class BuildconfigLastCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if busy:
            print("busy")
            return
        file = self.view.file_name() or self.view.window().folders()[0]
        sublime.active_window().run_command('save_all')
        config = load_config(file)
        if not config:
            return
        if self.view.file_name() in last_target_by_file:
            target = config.get_target_by_name(last_target_by_file[file])
            if target:
                perform_target(target, file)
                return
        self.view.run_command('build_config_run')

class BuildconfigRunCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if busy:
            print("busy")
            return
        file = self.view.file_name() or self.view.window().folders()[0]
        sublime.active_window().run_command('save_all')
        config = load_config(file)
        if not config:
            return
        targets = config.get_targets_for_file(file) + config.get_global_targets()
        if not targets:
            return
        options = [i.name for i in targets]
        def on_selection(index):
            if index == -1: return
            target = config.get_target_by_name(options[index])
            perform_target(target, file)
        if len(options) == 1 and config.get_target_by_name(options[0]).files:
            on_selection(0)
        else:
            self.view.window().show_quick_panel(options, on_selection)

