import sys
import time

import pkg_resources
import Image
import tg
from pylons import c
from paste.deploy.converters import asint

from ming.orm import MappedClass, mapper, ThreadLocalORMSession, session, state
from . import base
import forgetracker.model


class RethumbCommand(base.Command):
    min_args=1
    max_args=2
    usage = '<ini file> [<project name>]'
    summary = 'Recreate thumbnails for attachment images'
    parser = base.Command.standard_parser(verbose=True)
    parser.add_option('', '--force', dest='force', action='store_true',
                      help=('Recreate all thumbnails (by first removing any existing)'))

    created_thumbs = 0

    def create_thumbnail(self, attachment, att_cls):
        if attachment.is_image():
            base.log.info("Processing image attachment '%s'", attachment.filename)
            doc = state(attachment).document.deinstrumented_clone()
            del doc['_id']
            del doc['file_id']
            doc['type'] = 'thumbnail'
            count = att_cls.query.find(doc).count()
            if count == 1:
                base.log.info("Thumbnail already exists for '%s' - skipping", attachment.filename)
                return
            elif count > 1:
                base.log.warning("There are %d thumbnails for '%s' - consider clearing them with --force", count, attachment.filename)
                return

            image = Image.open(attachment.rfile())
            del doc['content_type']
            del doc['filename']
            att_cls.save_thumbnail(attachment.filename, image, attachment.content_type, att_cls.thumbnail_size, doc, square=True)
            base.log.info("Created thumbnail for '%s'", attachment.filename)
            self.created_thumbs += 1

    def process_att_of_type(self, cls, find_criteria):
        base.log.info('Processing attachment class: %s', cls)
        find_criteria['type'] = 'attachment'
        for att in cls.query.find(find_criteria):
            self.create_thumbnail(att, cls)

    def command(self):
        from allura import model as M
        self.basic_setup()

        base.log.info('Collecting application attachment classes')
        package_model_map = {}
        for name, cls in MappedClass._registry.iteritems():
            if issubclass(cls, M.BaseAttachment):
                if cls.__mongometa__.session is M.project_orm_session:
                    package = cls.__module__.split('.', 1)[0]
                    l = package_model_map.get(package, [])
                    l.append(cls)
                    package_model_map[package] = l

        if len(self.args) > 1:
            projects = M.Project.query.find({'shortname': self.args[1]})
        else:
            projects = M.Project.query.find()
        for p in projects:
            base.log.info('=' * 20)
            base.log.info("Processing project '%s'", p.shortname)
            c.project = p

            if self.options.force:
                existing_thumbs = M.BaseAttachment.query.find({'type': 'thumbnail'}).count()
                base.log.info('Removing %d current thumbnails (per --force)', existing_thumbs)
                M.BaseAttachment.query.remove({'type': 'thumbnail'})

            # ProjectFile's live in main collection (unlike File's)
            # M.ProjectFile.query.find({'app_config_id': None, 'type': 'attachment'}).all()

            for app in p.app_configs:
                base.log.info("Processing application '%s' mounted at '%s' of type '%s'", app.options['mount_label'], app.options['mount_point'], app.tool_name)

                # Any application may contain DiscussionAttachment's, it has discussion_id field
                self.process_att_of_type(M.DiscussionAttachment, {'app_config_id': app._id, 'discussion_id': {'$ne': None}})

                # Otherwise, we'll take attachment classes belonging to app's package
                ep = pkg_resources.iter_entry_points('allura', app.tool_name).next()
                app_package = ep.module_name.split('.', 1)[0]
                if app_package == 'allura':
                    # Apps in allura known to not define own attachment types
                    continue

                classes = package_model_map.get(app_package, [])
                for cls in classes:
                    self.process_att_of_type(cls, {'app_config_id': app._id, 'discussion_id': None})

                base.log.info('-' * 10)

        base.log.info('Recreated %d thumbs', self.created_thumbs)
        if self.options.force:
            if existing_thumbs != self.created_thumbs:
                base.log.warning('There were %d thumbs before --force operation started, but %d recreated', existing_thumbs, self.created_thumbs)

        ThreadLocalORMSession.flush_all()
