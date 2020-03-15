"""Automated grading of programming assignments.
"""
import os, os.path, sys
import logging, threading, subprocess, itertools, collections
from contextlib import contextmanager

__author__  = 'David Menendez'
__version__ = '3.0.1'

logger = logging.getLogger(__name__)

NORMAL, EXTRA, USER = range(3)
category_names = ['Regular credit', 'Extra credit', 'Personal (not graded)']

class Error(Exception):
    def report(self, ctx):
        print()
        print(ctx + ':', *self.args)

class CommandError(Error):
    def __init__(self, cmd, code, out=None):
        self.cmd = cmd
        self.code = code
        self.out = out

    def report(self, ctx):
        print()
        print(f'{ctx}: error running {self.cmd[0]!r} (return code {self.code})')
        if len(self.cmd) > 1:
            print('  arguments', self.cmd[1:])
        if self.out is not None:
            print(self.out)

# TODO: option to run non-silently
def run_command(cmd):
    """Execute a command without a timeout. Useful for calling make.
    """
    logger.debug('Running %s', cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='latin-1')
    (out,err)= p.communicate()

    if out:
        logger.debug('Response\n%s', out)

    if p.returncode != 0:
        raise CommandError(cmd, p.returncode, out)

# --

class TestReporter:
    def __init__(self, **kws):
        self.requested_tests = 0
        self.completed_tests = 0
        self.failures = 0
        self.errors = 0
        self.points = 0
        self.score = 0

        self.show_successes = kws.get('show_successes', False)
        self.show_comments = kws.get('show_comments', True)
        self.show_input = kws.get('show_input', True)
        self.show_output = kws.get('show_output', True)

        self.show_status = kws.get('show_status', True)
        self.bar_visible= False


    def clear_bar(self):
        if self.bar_visible:
            sys.stderr.write('\r')
            sys.stderr.write(' ' * 80)
            sys.stderr.write('\r')
            self.bar_visible = False

    def set_status(self, status_msg):
        if self.show_status:
            sys.stderr.write('\r')
            sys.stderr.write(status_msg)
            sys.stderr.write(' ' * (80 - len(status_msg)))
            self.bar_visible = True

        else:
            print(status_msg)

    def message(self, msg):
        self.clear_bar()
        print()
        print(msg)

    def begin_test(self, crnt_test):
        self.crnt_test = crnt_test
        self.refresh()


    def refresh(self):
        if self.show_status:
            if self.errors:
                msg = f'\rCompleted {self.completed_tests} of {self.requested_tests}. Failures {self.failures}. Errors {self.errors}.'
            else:
                msg = f'\rCompleted {self.completed_tests} of {self.requested_tests}. Failures {self.failures}.'

            sys.stderr.write(msg)
            self.bar_visible = True

reporter = None

def get_reporter():
    global reporter
    if reporter is None:
        reporter = TestReporter()

    return reporter

# --

class Test:
    time_limit   = 30
    output_limit = 16*1024
    error_limit  = 5
    encoding     = 'latin-1'  # less vulnerable to student bugs than ASCII

    def __init__(self, cmd, dir = None, group = '', weight = 1, category = NORMAL, ref_code = 0):
        if not cmd:
            raise ValueError(f"Attempt to create {type(self)} with empty command")

        self.dir = dir
        self.cmd = cmd
        self.group = group
        self.weight = weight
        self.category = category
        self.ref_code = ref_code

    def run(self):
        """Perform the test and report the number of successes.
        """
        logger.debug('Running %s: %s', self.group, self.cmd)

        self.summary = ''
        self.comments = []

        self.prepare()

        p = subprocess.Popen(self.cmd,
            stdin    = subprocess.PIPE,
            stdout   = subprocess.PIPE,
            stderr   = subprocess.STDOUT,
            encoding = self.encoding)

        def cancel():
            p.kill()
            self.summary = 'timed out'

        timer = threading.Timer(self.time_limit, cancel)

        try:
            self.handle_stdin(p.stdin)
            timer.start()
            out = p.stdout.read(self.output_limit)
            if p.stdout.read(1):
                p.kill()
                self.summary = 'exceeded output limit'

            # make sure we get the final exit code. if we got here, p has either closed
            # stdout or been killed.
            p.wait()
        finally:
            timer.cancel()

        logger.debug('Complete. Code %s\n%s', p.returncode, out)

        if p.returncode == self.ref_code:
            self.analyze_output(out)
        else:
            self.summary = 'unexpected return code: ' + str(p.returncode)
            self.check_for_sanitizer_output(p.pid, out)


        success = not self.summary

        reporter = get_reporter()

        if success and reporter.show_successes:
            self.summary = 'correct'

        if self.summary:
            reporter.clear_bar()

            print()
            print(f'{self.group}: {self.summary}')
            print(f'   arguments {self.cmd}')

            if reporter.show_comments:
                print()
                for line in self.comments:
                    print('  ', line)

            if reporter.show_input:
                self.print_input()

            if reporter.show_output:
                print()
                print('output')
                print('---')
                print(out, end='')
                print('---')

        del self.summary
        del self.comments

        return (success, self.weight if success else 0)


    def prepare(self):
        if self.dir is not None:
            logger.debug('Moving to %r', self.dir)
            os.chdir(self.dir)

    def handle_stdin(self, proc_stdin):
        proc_stdin.close()

    def print_input(self):
        pass

    def analyze_output(self, out):
        pass

    def check_for_sanitizer_output(self, pid, output):
        """Detect error messages from AddressSanitizer.
        """

        keyword = f'=={pid}=='
        logger.debug('Checking for %r', keyword)

        lines = iter(output.split('\n'))
        for line in lines:
            if line.startswith(keyword):
                if 'AddressSanitizer' in line:
                    self.summary = 'terminated by AddressSanitizer'
                break
        else: # not found
            return

        # continue searching for SUMMARY
        for line in lines:
            if line.startswith('SUMMARY:'):
                self.comments = [line]
                return

class RefTest(Test):
    """Compare program output with a specified reference string.
    """
    def __init__(self, cmd, ref, **kws):
        super().__init__(cmd, **kws)
        self.ref = ref

    def analyze_output(self, full_out):
        out = full_out.split('\n', 1)[0].rstrip()
        if out != self.ref:
            self.summary = 'incorrect output'
            self.comments += [
                'expected: ' + self.ref,
                'received: ' + out]

class FileRefTest(Test):
    """Compare program output with a reference file.
    """
    def __init__(self, cmd, ref_file, **kws):
        super().__init__(cmd, **kws)
        self.ref_file = ref_file

    def analyze_output(self, out):
        try:
            logger.debug('Opening reference file %r', self.ref_file)
            self.comments.append('reference file: ' + repr(self.ref_file))

            reflines = open(self.ref_file).read().rstrip().split('\n')
            outlines = out.rstrip().split('\n')

            logger.debug('out %d lines; ref %d lines', len(outlines), len(reflines))

            errors = [(i,refl,outl) for (i,(refl,outl))
                        in enumerate(zip(reflines, outlines), 1)
                        if refl != outl]

            if self.error_limit and len(errors) > self.error_limit:
                errs = len(errors) - self.error_limit
                errors = errors[:self.error_limit]
            else:
                errs = 0

            errors = list(itertools.chain.from_iterable(
                ['line {:,}'.format(i),
                 '  expected: ' + repr(refl),
                 '  received: ' + repr(outl)] for (i,refl,outl) in errors))

            if errs:
                errors.append('{:,} additional errors'.format(errs))

            if len(reflines) < len(outlines):
                errors += ['{:,} extra lines in output'.format(
                    len(outlines) - len(reflines))]
            elif len(reflines) > len(outlines):
                errors += [
                    'line {:,}'.format(len(outlines)+1),
                    '  expected: ' + repr(reflines[len(outlines)]),
                    '  received end of file']

            if errors:
                self.summary = 'incorrect output'

            self.comments += errors

        except IOError as e:
            raise Error(f'Unable to open reference file {self.ref_file!r}: {e.strerror}')

class InputFileTest(Test):
    """Test with a specified input given by input_file.
    """
    def __init__(self, cmd, input_file, **kws):
        super().__init__(cmd, **kws)
        self.input_file = input_file

    def print_input(self):
        try:
            logger.debug('Opening input file %r', self.input_file)
            input = open(self.input_file).read().rstrip()

            print()
            print('input')
            print('-----')
            print(input)
            print('-----')

        except IOError as e:
            raise Error('Unable to open input file {}: {}'.format(
                self.input_file, e.strerror))

class FileTest(FileRefTest, InputFileTest):
    """Tests with specified input and reference files.
    """
    pass

class InputFileStdinTest(InputFileTest):
    """Test with a specified input given by input_file. Input file is send to the
    process on stdin.
    """
    def handle_stdin(self, stdin):
        try:
            logger.debug('Opening input file %r', self.input_file)
            self.comments.append('input file: ' + repr(self.input_file))
            with open(self.input_file) as f:
                stdin.write(f.read())
        except IOError as e:
            raise Error(f'Unable to send input file {self.input_file!r}: {e.strerror}')
        finally:
            stdin.close()

class StdinTest(InputFileStdinTest, FileTest):
    """Test with specified input and reference files. The input is is sent to the process
    on stdin.
    """
    pass

# --

class AbstractTestGroup:
    @classmethod
    def Project(cls, name, *args, **kws):
        tests = cls(*args, **kws)
        return Project(name, tests)

    def __init__(self, id='', weight=1, name=None, category=NORMAL, make_cmd=None):
        self.id = id
        self.name = name or id
        self.weight = weight
        self.category = category

        if make_cmd:
            self.make_cmd = make_cmd

    def get_tests(self, project, prog, build_dir, data_dir):
        raise NotImplementedError

    @staticmethod
    def make_cmd(prog, arg):
        return [prog, arg]

class StringTests(AbstractTestGroup):
    """Look for tests in a file named <prefix><id><suffix>.
    """
    def __init__(self, prefix='tests', suffix='.txt', **kws):
        super().__init__(**kws)
        self.file = prefix + (self.id or '') + suffix

    Test = RefTest

    def get_tests(self, project, prog, build_dir, data_dir):
        test_group = project + ':' + self.name if self.name else project

        test_file = os.path.join(data_dir, self.file)

        if not os.path.exists(test_file):
            logger.warning('Test file not found: %r', test_file)
            return

        logger.debug('Opening tests file: %r', test_file)

        with open(test_file) as lines:
            try:
                while True:
                    arg = next(lines).rstrip()
                    ref = next(lines).rstrip()

                    yield self.Test(cmd      = self.make_cmd('./' + prog, arg),
                                    ref      = ref,
                                    category = self.category,
                                    group    = test_group,
                                    weight   = self.weight,
                                    dir      = build_dir)

            except StopIteration:
                return


class FileTests(AbstractTestGroup):
    """Look for pairs of test files containing reference and input data.
    If id is None, they are named:
        <arg_prefix><test><suffix>
        <ref_prefix><test><suffix>

    Otherwise, they are named:
        <arg_prefix><id>.<test><suffix>
        <ref_prefix><id>.<test><suffix>
    """

    def __init__(self, arg_prefix='test.', ref_prefix='ref.', suffix='.txt', **kws):
        super().__init__(**kws)
        self.suffix = suffix

        if self.id:
            self.arg_prefix = f'{arg_prefix}{self.id}.'
            self.ref_prefix = f'{ref_prefix}{self.id}.'
        else:
            self.arg_prefix = arg_prefix
            self.ref_prefix = ref_prefix

    Test = FileTest

    def get_tests(self, project, prog, build_dir, data_dir):
        test_group = project + ':' + self.name if self.name else project

        # gather the names of the reference files
        fnames = [fname for fname in os.listdir(data_dir)
                    if fname.startswith(self.ref_prefix)
                    and fname.endswith(self.suffix)]
        fnames.sort()

        prog = './' + prog

        # for each reference name, find the corresponding input file
        for ref_name in fnames:
            # swap ref_prefix for arg_prefix
            arg_name = self.arg_prefix + ref_name[len(self.ref_prefix):]

            arg = os.path.join(data_dir, arg_name)

            if not os.path.exists(arg):
                logger.warning('Unmatched reference file: %r', ref_name)
                continue

            ref = os.path.join(data_dir, ref_name)

            yield self.Test(cmd        = self.make_cmd(prog, arg),
                            input_file = arg,
                            ref_file   = ref,
                            category   = self.category,
                            group      = test_group,
                            weight     = self.weight,
                            dir        = build_dir)


class StdinFileTests(FileTests):
    Test = StdinTest

    @staticmethod
    def make_cmd(prog, arg):
        return [prog]

# --

class Project:
    def __init__(self, name, *groups, **kws):
        self.tests = None
        self.name  = name
        self.prog  = kws.get('prog_name', self.name)
        self.ready = False

        # make sure groups have distinct names
        groupids = collections.Counter(g.id for g in groups)
        if len(groupids) < len(groups):
            raise ValueError('Duplicate test group ids for ' + name + ': ' +
                str([g for g in groupids if groupids[g] > 1]))

        # separate regular and user test groups
        self.groups = tuple(g for g in groups if g.category != USER)

        if not self.groups:
            raise ValueError('Must provide at least one test group')

        self.user_groups = tuple(g for g in groups if g.category == USER)

        # generate a user group if none are specified
        if not self.user_groups:
            user_class = kws.get('user_class', type(self.groups[0]))
            if user_class is not None:
                self.user_groups = ( user_class(name='0', category=USER) ,)

    def has_context(self):
        return hasattr(self, 'src_dir') \
            and hasattr(self, 'build_dir') \
            and hasattr(self, 'data_dir') \
            and hasattr(self, 'user_dir')

    def set_context(self, src_dir, build_dir, data_dir, user_dir=None):
        self.src_dir = src_dir
        self.build_dir = build_dir
        self.data_dir = data_dir
        self.user_dir = \
            os.path.join(src_dir, 'tests') if user_dir is None else user_dir

    def gather_tests(self, requests):
        if not self.has_context():
            raise Exception('Attempt to gather tests without context')

        logger.info('Gathering tests for %r', self.name)
        if not os.path.isdir(self.src_dir):
            get_reporter().message(f'No source found for {self.name}')
            logger.info('Source dir not found: %r', self.src_dir)
            return 0

        if not os.path.isdir(self.data_dir):
            raise Error('Data directory not found: ' + repr(self.data_dir))

        # if project is requested by name, then all groups are requested
        if self.name in requests:
            requests = ()

        self.tests = []
        for group in self.groups:
            if not requests or f'{self.name}:{group.name}' in requests:
                self.tests.extend(group.get_tests(self.name, self.prog, self.build_dir, self.data_dir))

        if self.user_groups and os.path.isdir(self.user_dir):
            for group in self.user_groups:
                if not requests or f'{self.name}:{group.name}' in requests:
                    self.tests.extend(group.get_tests(self.name, self.prog, self.build_dir, self.user_dir))

        count = len(self.tests)
        logger.info('Total tests for %s: %s', self.name, count)
        return count

    def prepare_build_dir(self):
        "Ensure that build_dir exists and contains the Makefile"

        if not self.tests:
            return

        os.makedirs(self.build_dir, exist_ok=True)
        Makefile = os.path.join(self.build_dir, 'Makefile')
        if not os.path.exists(Makefile):  # TODO: option to force overwrite
            logger.info('Creating Makefile: %r', Makefile)

            srcpath = os.path.relpath(self.src_dir, self.build_dir)

            if ' ' in srcpath:
                raise Error('space in path from SRC_DIR to BUILD_DIR ' + repr(srcpath))

            with open(Makefile, 'w') as f:
                f.write(f'''SRCPATH={srcpath}

vpath %.c $(SRCPATH)
vpath %.h $(SRCPATH)

include $(SRCPATH)/Makefile
''')


    def clear(self):
        "Run make clean in the object directory"
        if not hasattr(self, 'build_dir'):
            raise Exception('Attempt to clear without context')

        os.chdir(self.build_dir)
        run_command(['make', 'clean'])

    def build(self, clear=False):
        "Run make in the build directory"
        if not self.tests:
            return

        if not hasattr(self, 'build_dir'):
            raise Exception('Attempt to build without context')

        get_reporter().set_status(f'Building {self.name}.')

        try:
            #os.makedirs(self.build_dir, exist_ok=True)
            os.chdir(self.build_dir)

            if clear:
                self.clear()

            run_command(['make'])
            if not os.path.exists(self.prog):
                raise Error('executable not created: ' + self.prog)

            self.ready = True

        except Error as e:
            reporter = get_reporter()
            reporter.errors += 1
            reporter.clear_bar()

            e.report(self.name)

    def get_tests(self):
        return self.tests if self.ready else []



class MultiProject:
    def __init__(self, *projects):
        self.projects = projects
        self.context = False

        names = collections.Counter(p.name for p in projects)
        if len(names) < len(projects):
            raise ValueError('Duplicate project names ' +
                 str([p for p in names if names[p] > 1]))

    def has_context(self):
        return self.context

    def set_context(self, src_dir, build_dir, data_dir):
        for p in self.projects:
            p.set_context(
                os.path.join(src_dir, p.name),
                os.path.join(build_dir, p.name),
                os.path.join(data_dir, p.name))
        self.context = True

    def prepare_build_dir(self):
        for p in self.projects:
            p.prepare_build_dir()

    def clear(self):
        for p in self.projects:
            p.clear()

    def build(self, clear=False):
        for p in self.projects:
            p.build(clear)

    def gather_tests(self, requests):
        count = 0

        for p in self.projects:
            count += p.gather_tests(requests)

        logger.info('Total tests: %s', count)
        return count

    def get_tests(self):
        return itertools.chain.from_iterable(p.get_tests() for p in self.projects)


# --

import time

def test_project(project, src_dir, build_dir, data_dir, fail_stop=False, requests=(), init_only=False):
    """Fully run tests for a project, using the specified directory roots.
    """

    reporter = get_reporter()

    project.set_context(src_dir, build_dir, data_dir)

    logger.debug('gather phase')
    reporter.requested_tests = project.gather_tests(requests)
    # TODO: filter test cases by request

    if reporter.requested_tests < 1:
        reporter.message('No tests requested.')
        return

    logger.debug('build_dir prep phase')
    project.prepare_build_dir()

    if init_only:
        return

    logger.debug('build phase')
    project.build()

    if fail_stop and reporter.errors:
        reporter.message('grader: abort.')
        return

    logger.debug('test phase')
    points = collections.defaultdict(collections.Counter)
    scores = collections.defaultdict(collections.Counter)
    failures = collections.defaultdict(collections.Counter)

    for t in project.get_tests():
        points[t.category][t.group] += t.weight
        try:
            reporter.begin_test(t.group)
            (success, credit) = t.run()

            reporter.completed_tests += 1
        except Error as e:
            reporter.errors += 1
            reporter.clear_bar()
            e.report(t.group)
            success = False
            credit = 0

        if not success:
            reporter.failures += 1
            failures[t.category][t.group] += 1
            if fail_stop:
                reporter.message(f'grader: aborting. Completed {reporter.completed_tests} of {reporter.requested_tests}.')
                return

        scores[t.category][t.group] += credit


    logger.debug('report phase')

    reporter.clear_bar()
    print()
    print('Tests performed:', reporter.completed_tests, 'of', reporter.requested_tests)
    print('Tests failed:   ', reporter.failures)
    if reporter.errors:
        print('Errors:         ', reporter.errors)

    for category,catscores in scores.items():
        cat_score = 0
        cat_points = 0

        group_width = max(5, max(len(g) for g in catscores))

        reporter.clear_bar()
        print()
        print(category_names[category])
        print('-----')
        print(f'  {"":{group_width}} Points Failed Score')
        for group,score in catscores.items():
            failed       = failures[category][group] or ''
            group_points = points[category][group]
            cat_points += group_points
            cat_score  += score

            print(f'  {group:{group_width}} {group_points:6.1f} {failed:6} {score:5.1f}')

        if len(catscores) > 1:
            print(f'  {"":{group_width}} ------        -----')
            print(f'  {"":{group_width}} {cat_points:6.1f}        {cat_score:5.1f}')


logcfg = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'normal': { 'format': '%(asctime)s %(levelname)-8s %(message)s' },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            #'filename': 'autograder.log',
            'filename': os.path.join(sys.path[0], 'autograder.log'),
            'mode': 'a',
            'formatter': 'normal',
            'delay': True,
        },
    },
    'root': {
        'handlers': ['file'],
    },
}

def get_args(src_subdir):
    import argparse

    argp = argparse.ArgumentParser()
    argp.add_argument('-1', '--stop', action='store_true',
        help='Stop after the first error. Increases verbosity.')
    argp.add_argument('-v', '--verbose', action='count', default=0,
        help='Print more output')
    argp.add_argument('-q', '--quiet', action='count', default=0,
        help='Print less output'),
    argp.add_argument('-i', '--init', action='store_true',
        help='Create the build directory, but do not compile or test')
    argp.add_argument('-f', '--fresh', action='store_true',
        help='Delete object directory and rebuild before testing')
    argp.add_argument('-s', '--src', metavar='dir', default=src_subdir,
        help='Directory containing program files')
    argp.add_argument('-b', '--build', metavar='dir', default=None,
        help='Directory to place object files')
    argp.add_argument('-a', '--archive', metavar='tar',
        help='Archive containing program files (overrides -s and -o)')
#     argp.add_argument('-x', '--extra', action='store_true',
#         help='Include extra credit tests')
#     argp.add_argument('-m', '--multiply', nargs=2, metavar=('project','factor'),
#         action='append', default=[],
#         help='Multiply a particular project score by some factor.')
    argp.add_argument('-d', '--debug', action='store_true',
        help='Increase logging')
    argp.add_argument('program', nargs='*',
        help='Name of program to grade')

    return argp.parse_args()

@contextmanager
def temp_dir():
    """Create a temporary directory, and delete it and its contents once
    the context has been closed. Yields the directory path
    """
    import tempfile, shutil

    dir = tempfile.mkdtemp()
    try:
        logger.debug('Created temporary directory: %r', dir)
        yield dir

    finally:
        logger.debug('Deleting temporary directory')
        shutil.rmtree(dir)


def main(name, assignment, release=1,
    src_subdir = 'src',
    build_subdir = 'build',
    data_subdir = 'data',
    logcfg = logcfg):

    import logging.config

    args = get_args(src_subdir)

    if logcfg:
        logging.config.dictConfig(logcfg)

    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info('Starting autograder %s release %s. Library %s',
        name, release, __version__)

    # data directory is relative to grader
    data_dir = os.path.join(sys.path[0], data_subdir)

    logger.debug('Data directory: %r', data_dir)

    reporter = get_reporter()
    verb = args.verbose - args.quiet
    if args.stop:
        verb += 1

    if args.build:
        build_subdir = args.build

    logger.debug('Verbosity level: %s', verb)

    if verb < 0:
        reporter.show_comments = False
    if verb < 1:
        reporter.show_input = False
        reporter.show_output = False
    if verb > 1:
        reporter.show_successes = True

    kws = {
        'fail_stop': args.stop,
        'requests': set(args.program),
        'init_only': args.init,
    }

    try:
        reporter.clear_bar()
        print(f'{name} Auto-grader, Release {release}')

        if args.archive:
            archive = os.path.realpath(args.archive)
            logger.debug('Archive path: %r', archive)

            if not os.path.exists(archive):
                raise Error('archive not found: ' + repr(archive))

            with temp_dir() as dir:
                os.chdir(dir)
                run_command(['tar', '-xf', archive])

                if not os.path.isdir(src_subdir):
                    raise Error('archive does not contain directory ' + repr(src_subdir))

                if os.path.exists(build_subdir):
                    reporter.message(f'WARNING: archive contains {build_subdir!r}')
                    import shutil
                    shutil.rmtree(build_subdir)

                os.mkdir(build_subdir)

                src_dir   = os.path.realpath(src_subdir)
                build_dir = os.path.realpath(build_subdir)

                test_project(assignment, src_dir, build_dir, data_dir, **kws)

        else:
            src_dir = os.path.realpath(args.src)

            logger.debug('Source directory: %r', src_dir)

            if not os.path.isdir(src_dir):
                raise Error('invalid src directory: ' + repr(src_dir))

            # TODO: some control about how the build directory is handled
            build_dir = os.path.realpath(build_subdir)

            logger.debug('Build directory: %r', build_dir)

            if args.fresh and os.path.isdir(build_dir):
                import shutil
                logger.info('Removing build_dir: %r', build_dir)
                shutil.rmtree(build_dir)

            test_project(assignment, src_dir, build_dir, data_dir, **kws)

    except Error as e:
        reporter.clear_bar()
        e.report('grader')
        exit(1)
    except Exception as e:
        logger.exception('Uncaught exception: %s', e)
        reporter.clear_bar()
        print('grader: internal error')
        exit(1)

if __name__ == '__main__':
    import logging.config
    logging.config.dictConfig(logcfg)

    proj = MultiProject(
            StringTests.Project(name='roman'),
            StringTests.Project(name='pal'))

    reporter = TestReporter(show_successes=False)

    test_project(proj, os.path.realpath('src'), os.path.realpath('obj'), os.path.realpath('data'))
