import os
import base
from allura.command import base as allura_base

from pylons import c

from allura import model as M
from allura.lib import exceptions

from forgewiki.command.wiki2markdown_pages import PagesImportUnit
from forgewiki.command.wiki2markdown_history import HistoryImportUnit
from forgewiki.command.wiki2markdown_attachments import AttachmentsImportUnit
from forgewiki.command.wiki2markdown_talk import TalkImportUnit


class Wiki2MarkDownCommand(base.WikiCommand):
    min_args=1
    max_args=None
    summary = 'Export mediawiki to markdown'
    all_import_units = [
        "pages",
        "history",
        "attachments",
        "talk"
    ]
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('-e', '--extract-only', action='store_true', dest='extract',
                      help='Store data from the Allura mediawiki content on the local filesystem; not load into Allura')
    parser.add_option('-l', '--load-only', action='store_true', dest='load',
                      help='Load into Allura previously-extracted data')
    parser.add_option('-o', '--output-dir', dest='output_dir', default='',
                      help='directory for dump files')

    def command(self):
        self.basic_setup()

        if self.options.output_dir == '':
            allura_base.log.error("You must specify output directory")
            exit(2)

        if self.options.load is None and self.options.extract is None:
            allura_base.log.error('You must set action. Extract or load the data')
            exit(2)

        import_units = self.args[1:]
        if len(import_units) == 0:
            import_units = self.all_import_units
        else:
            for el in import_units:
                if el not in self.all_import_units:
                    allura_base.log.error("%s import unit was not found" % el)
                    exit(2)

        if not os.path.exists(self.options.output_dir):
            os.makedirs(self.options.output_dir)

        for uname in import_units:
            if uname == "pages":
                iu = PagesImportUnit(self.options)

            elif uname == "history":
                iu = HistoryImportUnit(self.options)

            elif uname == "attachments":
                iu = AttachmentsImportUnit(self.options)

            elif uname == "talk":
                iu = TalkImportUnit(self.options)

            if self.options.extract:
                iu.extract()
            elif self.options.load:
                iu.load()
