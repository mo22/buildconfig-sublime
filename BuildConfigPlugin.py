# [ ] last_target_by_file store only names
# [ ] def load_config: load / reload config, cached, background thread?
# [ ] perform_command should wait

# https://www.sublimetext.com/docs/3/api_reference.html#sublime.View
# http://docs.sublimetext.info/en/latest/reference/commands.html

import sys
import os
import sublime
import sublime_plugin
import pipes
import subprocess
from . import buildconfig
from . import runpersistent

last_target_by_file = {}

def load_config(view):
    pass

def perform_command(command, view):
    print(">", command)
    view.show_popup(repr(command))
    cmd = [command.get_shell()] if command.is_shell() else command.get_cmd()
    cwd = command.get_cwd()
    env = command.get_env()
    if command.persistent:
        if sys.platform == 'darwin' or sys.platform == 'linux':
            if sys.platform == 'darwin':
                sessioncmd = os.path.join(os.path.dirname(os.path.abspath(buildconfig.__file__)), 'background-process-darwin.sh')
            elif sys.platform == 'linux':
                sessioncmd = os.path.join(os.path.dirname(os.path.abspath(buildconfig.__file__)), 'background-process-screen.sh')
            if command.restart:
                try:
                    subprocess.check_call([
                        'sh',
                        sessioncmd,
                        'kill',
                        command.get_persistent_id()
                    ])
                except:
                    pass
            shell = ''
            shell += "cd %s\n" % pipes.quote(cwd)
            for (k, v) in env.items():
                shell += "export %s=%s\n" % (k, pipes.quote(v))
            if command.is_shell():
                shell += command.shell + "\n"
            else:
                shell += ' '.join(pipes.quote(i) for i in cmd) + "\n"
            subprocess.check_call([
                'sh',
                sessioncmd,
                'open',
                command.get_persistent_id(),
                shell
            ])
        elif sys.platform == 'win32':
            raise NotImplementedError('not implemented')
        else:
            raise NotImplementedError('not implemented')
    else:
        view.window().run_command('exec', {
            'cmd': cmd,
            'working_dir': cwd,
            'quiet': True,
            'shell': command.is_shell(),
            'env': env
        })
        # @TODO: wait for it??


def perform_target(target, view):
    last_target_by_file[view.file_name()] = target
    target._config.params['file'] = view.file_name()
    for command in target.get_commands():
        perform_command(command, view)


class BuildConfigLastCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not self.view.file_name(): return
        sublime.active_window().run_command('save_all')
        if self.view.file_name() in last_target_by_file:
            perform_target(last_target_by_file[self.view.file_name()], self.view)
        else:
            self.view.run_command('build_config_run')



class BuildConfigRunCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if not self.view.file_name(): return
        sublime.active_window().run_command('save_all')
        try:
            config = buildconfig.BuildConfig.load_at_path(self.view.file_name())
        except Exception as e:
            self.view.show_popup('BuildConfig error: ' + str(e), max_width=500)
            raise
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

