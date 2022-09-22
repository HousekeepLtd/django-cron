Sample Cron Configurations
==========================

Retry after failure feature
---------------------------

You can run cron by passing ``RETRY_AFTER_FAILURE_MINS`` param.

This will re-runs not next time runcrons is run, but at least ``RETRY_AFTER_FAILURE_MINS`` after last failure:

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_EVERY_MINS = 60 # every hours
        RETRY_AFTER_FAILURE_MINS = 5

        schedule = Schedule(run_every_mins=RUN_EVERY_MINS, retry_after_failure_mins=RETRY_AFTER_FAILURE_MINS)


Run at times feature
--------------------

You can run cron by passing ``run_every_mins`` or ``run_at_times`` params.

``run_every_mins`` specifies the length of the interval between job starts, expressed in minutes.

This will run job every hour:

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_EVERY_MINS = 60 # every hours

        schedule = Schedule(run_every_mins=RUN_EVERY_MINS)

``run_at_times`` determines the exact start time of the job.

This will run job at given hours:

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_AT_TIMES = ['11:30', '14:00', '23:15']

        schedule = Schedule(run_at_times=RUN_AT_TIMES)

Hour format is ``HH:MM`` (24h clock). ``django-cron`` will interpret
these times in the local timezone of your site, as specified by
the ``TIME_ZONE`` setting.

You can also mix up both of these methods:

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_EVERY_MINS = 120 # every 2 hours
        RUN_AT_TIMES = ['6:30']

        schedule = Schedule(run_every_mins=RUN_EVERY_MINS, run_at_times=RUN_AT_TIMES)

This will run job every 2h plus one run at 6:30.


Run tolerance feature
---------------------

You can specify ``RUN_TOLERANCE_SECONDS`` param.

This parameter specifies a time window to run the job.

For example, consider a job that runs every 5 minutes and last time it was run at 00:00:00. For example, ``runcrons`` command
gets called every five minutes starting from 00:00:00.

Without this parameter, the job will be run next time at 00:10:00.

If ``RUN_TOLERANCE_SECONDS`` is set to non-zero value, the job will be run next time at 00:05:00. That makes job run period
more precise.

Usage example:

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_EVERY_MINS = 5

        schedule = Schedule(run_every_mins=RUN_EVERY_MINS, run_tolerance_seconds=RUN_TOLERANCE_SECONDS)


Run monthly feature
--------------------
``run_monthly_on_days`` specifies the day of the month on which the job should be run.

You have to combine ``run_monthly_on_days`` with  ``run_at_times`` or ``run_every_mins``.

You can set your job to run every month at particular day, for example at 6:30 on the 1st and 10th day of month.

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_MONTHLY_ON_DAYS = [1, 10]
        RUN_AT_TIMES = ['6:30']
        schedule = Schedule(run_monthly_on_days=RUN_MONTHLY_ON_DAYS, run_at_times=RUN_AT_TIMES)

Run weekly feature
--------------------
``run_weekly_on_days`` specifies the day of the week on which the job should be run.

Days of the week are numbered from 0 to 6 where 0 is Monday and 6 is Sunday.

You have to combine ``run_weekly_on_days`` with  ``run_at_times`` or ``run_every_mins``.

You can set your job to run every week at particular day, for example at Saturday and Sunday at 6:30.

.. code-block:: python

    class MyCronJob(CronJobBase):
        RUN_WEEKLY_ON_DAYS = [0, 6]
        RUN_AT_TIMES = ['6:30']
        schedule = Schedule(run_weekly_on_days=RUN_WEEKLY_ON_DAYS, run_at_times=RUN_AT_TIMES)


Remove succeeded cron job logs
--------------------
``remove_successful_cron_logs`` specifies whether old successful logs should be deleted when a new log is created. Default: False

.. code-block:: python

    class MyCronJob(CronJobBase):
        remove_successful_cron_logs = True
        RUN_AT_TIMES = ['6:30']
        schedule = Schedule(run_weekly_on_days=RUN_WEEKLY_ON_DAYS, run_at_times=RUN_AT_TIMES)


Allowing parallels runs
-----------------------

By default parallels runs are not allowed (for security reasons). However if you
want enable them just add:

.. code-block:: python

    ALLOW_PARALLEL_RUNS = True

in your CronJob class.


.. note:: Note this requires a caching framework to be installed, as per https://docs.djangoproject.com/en/dev/topics/cache/

If you wish to override which cache is used, put this in your settings file:

.. code-block:: python

    DJANGO_CRON_CACHE = 'cron_cache'


FailedRunsNotificationCronJob
-----------------------------

This sample cron job checks for any unreported failed jobs for each job class
provided in your ``CRON_CLASSES`` list, and reports them as necessary. The job
is set to run on each ``runcrons`` task, and the default process is to email
all the users specified in the ``ADMINS`` settings list when a job fails more
than 10 times in a row.

Install required dependencies: ``Django>=3.2.0``.

Add ``django_cron.cron.FailedRunsNotificationCronJob`` to *the end* of your
``CRON_CLASSES`` list within your settings file. ::

    CRON_CLASSES = [
        ...
        'django_cron.cron.FailedRunsNotificationCronJob'
    ]

To configure the minimum number of failures before a report, you can either
provide a global using the setting ``CRON_MIN_NUM_FAILURES``, or add
a ``MIN_NUM_FAILURES`` attribute to your cron class. For example: ::

    # In your settings module
    CRON_MIN_NUM_FAILURES = 5

    # Or in your cron module
    class MyCronJob(CronJobBase):
        RUN_EVERY_MINS = 10
        MIN_NUM_FAILURES = 3

        schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
        code = 'app.MyCronJob'

        def do(self):
            ... some action here ...

You can configure the email sender and recipients by providing the
``CRON_FAILURE_FROM_EMAIL`` and ``CRON_FAILURE_EMAIL_RECIPIENTS`` settings
respectively. ::

    CRON_FAILURE_FROM_EMAIL = 'cronreport@me.com'
    CRON_FAILURE_EMAIL_RECIPIENTS = ['foo@bar.com', 'x@y.com']

You can specify a custom email prefix by providing the ``FAILED_RUNS_CRONJOB_EMAIL_PREFIX``
setting. For example: ::

    FAILED_RUNS_CRONJOB_EMAIL_PREFIX = "[Server check]: "

Finally, you can subclass ``FailedRunsNotificationCronJob`` and define a custom
``report_failure()`` method if you'd like to report a failure in a different
way (e.g. via slack, text etc.). For example: ::

    class FailedNotifier(FailedRunsNotificationCronJob):
        def report_failure(self, cron_cls, failed_jobs):
            """
            Report in Slack that the given Cron job failed.
            """
            slack.post("ERROR - Cron job '{0}' failed.".format(cron_cls.code))
