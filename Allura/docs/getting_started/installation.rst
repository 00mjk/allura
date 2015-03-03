..     Licensed to the Apache Software Foundation (ASF) under one
       or more contributor license agreements.  See the NOTICE file
       distributed with this work for additional information
       regarding copyright ownership.  The ASF licenses this file
       to you under the Apache License, Version 2.0 (the
       "License"); you may not use this file except in compliance
       with the License.  You may obtain a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

       Unless required by applicable law or agreed to in writing,
       software distributed under the License is distributed on an
       "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
       KIND, either express or implied.  See the License for the
       specific language governing permissions and limitations
       under the License.

************
Installation
************


Our step-by-step setup instructions are in our INSTALL.markdown file.  You can read it online at https://forge-allura.apache.org/p/allura/git/ci/master/tree/INSTALL.markdown  You should be able to get Allura up and running in well under an hour by following those instructions.

For a faster and easier setup, see our `Vagrant/VirtualBox installation guide <https://forge-allura.apache.org/p/allura/wiki/Install%20and%20Run%20Allura%20-%20Vagrant/>`_

Configuring Optional Features
-----------------------------

The `development.ini` file has many options you can explore and configure.  It is geared towards development, so you will want to review
carefully and make changes for production use.

To run SVN and Git services, see the :doc:`scm_host` page.

Some features may be added as separate `Allura extensions <https://forge-allura.apache.org/p/allura/wiki/Extensions/>`_

Enabling inbound email
^^^^^^^^^^^^^^^^^^^^^^

Allura can listen for email messages and update tools and artifacts.  For example, every ticket has an email address, and
emails sent to that address will be added as comments on the ticket.  To set up the SMTP listener, run:

.. code-block:: bash

    nohup paster smtp_server development.ini > /var/log/allura/smtp.log &

By default this uses port 8825.  Depending on your mail routing, you may need to change that port number.
And if the port is in use, this command will fail.  You can check the log file for any errors.
To change the port number, edit `development.ini` and change `forgemail.port` to the appropriate port number for your environment.

SMTP in development
^^^^^^^^^^^^^^^^^^^

The following command can be used for quick and easy monitoring of smtp during development.
Just be sure the port matches the `smtp_port` from your `development.ini` (8826 by default).

.. code-block:: bash

    python -m smtpd -n -c DebuggingServer localhost:8826

This will create a new debugging server that discards messages and prints them to stdout.


Using LDAP
^^^^^^^^^^

Allura has a pluggable authentication system, and can use an existing LDAP system. In your config
file (e.g. :file:`development.ini`), there are several "ldap" settings to set:

* Change auth.method to: :samp:`auth.method = ldap`
* Set all the :samp:`auth.ldap.{*}` settings to match your LDAP server configuration. (:samp:`auth.ldap.schroot_name` won't be
  used, don't worry about it.)
* Keep :samp:`auth.ldap.autoregister = true` This means Allura will use existing users from your LDAP
  server.
* Set :samp:`auth.allow_user_registration = false` since your users already are present in LDAP.
* Change user_prefs_storage.method to :samp:`user_prefs_storage.method = ldap`
* Change :samp:`user_prefs_storage.ldap.fields.display_name` if needed (e.g. if display names are stored
  in a different LDAP attribute).

Restart Allura and you should be all set.  Now users can log in with their LDAP credentials and their
Allura records will be automatically created the first time they log in.

Note: if you want users to register new accounts into your LDAP system via Allura, you should turn
off :samp:`autoregister` and turn on :samp:`allow_user_registration`

Enabling RabbitMQ
^^^^^^^^^^^^^^^^^

For faster notification of background jobs, you can use RabbitMQ.  Assuming a base setup from the INSTALL, run these commands
to install rabbitmq and set it up:

.. code-block:: bash

    sudo aptitude install rabbitmq-server
    sudo rabbitmqctl add_user testuser testpw
    sudo rabbitmqctl add_vhost testvhost
    sudo rabbitmqctl set_permissions -p testvhost testuser ""  ".*" ".*"
    pip install amqplib==0.6.1 kombu==1.0.4

Then edit Allura/development.ini and change `amqp.enabled = false` to `amqp.enabled = true` and uncomment the other `amqp` settings.

If your `paster taskd` process is still running, restart it:

.. code-block:: bash

    pkill -f taskd
    nohup paster taskd development.ini > /var/log/allura/taskd.log &