#!/usr/bin/env python3

import autograde
import os, os.path, shutil

assignment_name = 'PA2'
release = '2'

link_possible = True

def link_or_copy(src, dst):
    global link_possible
    if link_possible:
        autograde.logger.debug('Linking %r to %r', src, dst)
        try:
            if os.path.exists(dst):
                os.remove(dst)
            os.link(src, dst)
            return
        except OSError as e:
            autograde.logger.info('Caught OSError after copy: %s', e)
            link_possible = False

    autograde.logger.debug('Copying %r to %r', src, dst)
    shutil.copy(src, dst)

class MLTest(autograde.FileRefTest):
    def __init__(self, train_file, data_file, **kws):
        super().__init__(**kws)
        self.train_file = train_file
        self.data_file  = data_file

    def prepare(self):
        super().prepare()
        link_or_copy(self.data_file, 'data')
        link_or_copy(self.train_file, 'train')
        self.comments += ['training file: ' + repr(self.train_file),
                          'data file:     ' + repr(self.data_file)]


class MLTests(autograde.AbstractTestGroup):
    def get_tests(self, project, prog, build_dir, data_dir):
        if self.name:
            test_group   = f'{project}:{self.name}'
            train_prefix = f'train.{self.name}.'
            data_prefix  = f'data.{self.name}.'
            ref_prefix   = f'ref.{self.name}.'

        else:
            test_group   = project
            train_prefix = 'train.'
            data_prefix  = 'data.'
            ref_prefix   = 'ref.'

        suffix ='.txt'

        fnames = [fname for fname in os.listdir(data_dir)
                   if fname.startswith(ref_prefix) and fname.endswith(suffix)]
        fnames.sort()

        for fname in fnames:
            id = fname[len(ref_prefix):]
            data_name  = data_prefix  + id
            train_name = train_prefix + id

            ref = os.path.join(data_dir, fname)

            data = os.path.join(data_dir, data_name)
            if not os.path.exists(data):
                autograde.logger.warning('Missing data file %r', data_name)
                continue

            train = os.path.join(data_dir, train_name)
            if not os.path.exists(ref):
                autograde.logger.warning('Missing training file %r', train_name)
                continue

            yield MLTest(cmd        = ['./'+prog, 'train', 'data'],
                         ref_file   = ref,
                         train_file = train,
                         data_file  = data,
                         category   = self.category,
                         group      = test_group,
                         weight     = self.weight,
                         dir        = build_dir)


assignment = MLTests.Project('estimate', weight=5)

if __name__ == '__main__':
    autograde.main(assignment_name, assignment, release)
