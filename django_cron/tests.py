import threading
from time import sleep
from datetime import timedelta

from mock import patch
from freezegun import freeze_time

from django import db
from django.test import TransactionTestCase
from django.core.management import call_command
from django.test.utils import override_settings
from django.test.client import Client
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from django_cron.cron import FailedRunsNotificationCronJob
from django_cron.helpers import humanize_duration
from django_cron.models import CronJobLog
import test_crons


class OutBuffer(object):
    def __init__(self):
        self._str_cache = ''
        self.content = []
        self.modified = False

    def write(self, *args):
        self.content.extend(args)
        self.modified = True

    def str_content(self):
        if self.modified:
            self._str_cache = ''.join((str(x) for x in self.content))
            self.modified = False

        return self._str_cache


def call(*args, **kwargs):
    """
    Run the runcrons management command with a supressed output.
    """
    out_buffer = OutBuffer()
    call_command('runcrons', *args, stdout=out_buffer, **kwargs)
    return out_buffer.str_content()


class DjangoCronTestCase(TransactionTestCase):
    def setUp(self):
        CronJobLog.objects.all().delete()

    success_cron = 'test_crons.TestSucessCronJob'
    error_cron = 'test_crons.TestErrorCronJob'
    five_mins_cron = 'test_crons.Test5minsCronJob'
    run_at_times_cron = 'test_crons.TestRunAtTimesCronJob'
    wait_3sec_cron = 'test_crons.Wait3secCronJob'
    does_not_exist_cron = 'ThisCronObviouslyDoesntExist'
    no_code_cron = 'test_crons.NoCodeCronJob'
    test_failed_runs_notification_cron = 'django_cron.cron.FailedRunsNotificationCronJob'


class BaseTests(DjangoCronTestCase):
    def assertReportedRun(self, job_cls, response):
        expected_log = u"[\N{HEAVY CHECK MARK}] {0}".format(job_cls.code)
        self.assertIn(expected_log.encode('utf8'), response)

    def assertReportedNoRun(self, job_cls, response):
        expected_log = u"[ ] {0}".format(job_cls.code)
        self.assertIn(expected_log.encode('utf8'), response)

    def assertReportedFail(self, job_cls, response):
        expected_log = u"[\N{HEAVY BALLOT X}] {0}".format(job_cls.code)
        self.assertIn(expected_log.encode('utf8'), response)

    def test_success_cron(self):
        logs_count = CronJobLog.objects.all().count()
        call(self.success_cron, force=True)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

    def test_failed_cron(self):
        logs_count = CronJobLog.objects.all().count()
        response = call(self.error_cron, force=True)
        self.assertReportedFail(test_crons.TestErrorCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

    def test_not_exists_cron(self):
        logs_count = CronJobLog.objects.all().count()
        response = call(self.does_not_exist_cron, force=True)
        self.assertIn('Make sure these are valid cron class names', response)
        self.assertIn(self.does_not_exist_cron, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count)

    @patch('django_cron.logger')
    def test_requires_code(self, mock_logger):
        response = call(self.no_code_cron, force=True)
        self.assertIn('does not have a code attribute', response)
        mock_logger.info.assert_called()

    @override_settings(DJANGO_CRON_LOCK_BACKEND='django_cron.backends.lock.file.FileLock')
    def test_file_locking_backend(self):
        logs_count = CronJobLog.objects.all().count()
        call(self.success_cron, force=True)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

    @patch.object(test_crons.TestSucessCronJob, 'do')
    def test_dry_run_does_not_perform_task(self, mock_do):
        response = call(self.success_cron, dry_run=True)
        self.assertReportedRun(test_crons.TestSucessCronJob, response)
        mock_do.assert_not_called()
        self.assertFalse(CronJobLog.objects.exists())

    @patch.object(test_crons.TestSucessCronJob, 'do')
    def test_non_dry_run_performs_task(self, mock_do):
        mock_do.return_value = 'message'
        response = call(self.success_cron)
        self.assertReportedRun(test_crons.TestSucessCronJob, response)
        mock_do.assert_called_once()
        self.assertEquals(1, CronJobLog.objects.count())
        log = CronJobLog.objects.get()
        self.assertEquals('message', log.message)
        self.assertTrue(log.is_success)

    def test_runs_every_mins(self):
        logs_count = CronJobLog.objects.all().count()

        with freeze_time("2014-01-01 00:00:00"):
            response = call(self.five_mins_cron)
        self.assertReportedRun(test_crons.Test5minsCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

        with freeze_time("2014-01-01 00:04:59"):
            response = call(self.five_mins_cron)
        self.assertReportedNoRun(test_crons.Test5minsCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

        with freeze_time("2014-01-01 00:05:01"):
            response = call(self.five_mins_cron)
        self.assertReportedRun(test_crons.Test5minsCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 2)

    def test_runs_at_time(self):
        logs_count = CronJobLog.objects.all().count()
        with freeze_time("2014-01-01 00:00:01"):
            response = call(self.run_at_times_cron)
        self.assertReportedRun(test_crons.TestRunAtTimesCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

        with freeze_time("2014-01-01 00:04:50"):
            response = call(self.run_at_times_cron)
        self.assertReportedNoRun(test_crons.TestRunAtTimesCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

        with freeze_time("2014-01-01 00:05:01"):
            response = call(self.run_at_times_cron)
        self.assertReportedRun(test_crons.TestRunAtTimesCronJob, response)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 2)

    def test_silent_produces_no_output_success(self):
        response = call(self.success_cron, silent=True)
        self.assertEquals(1, CronJobLog.objects.count())
        self.assertEquals('', response)

    def test_silent_produces_no_output_no_run(self):
        with freeze_time("2014-01-01 00:00:00"):
            response = call(self.run_at_times_cron, silent=True)
        self.assertEquals(1, CronJobLog.objects.count())
        self.assertEquals('', response)

        with freeze_time("2014-01-01 00:00:01"):
            response = call(self.run_at_times_cron, silent=True)
        self.assertEquals(1, CronJobLog.objects.count())
        self.assertEquals('', response)

    def test_silent_produces_no_output_failure(self):
        response = call(self.error_cron, silent=True)
        self.assertEquals('', response)

    def test_admin(self):
        password = 'test'
        user = User.objects.create_superuser(
            'test',
            'test@tivix.com',
            password
        )
        self.client = Client()
        self.client.login(username=user.username, password=password)

        # edit CronJobLog object
        call(self.success_cron, force=True)
        log = CronJobLog.objects.all()[0]
        url = reverse('admin:django_cron_cronjoblog_change', args=(log.id,))
        response = self.client.get(url)
        self.assertIn('Cron job logs', str(response.content))

    def run_cronjob_in_thread(self, logs_count):
        call(self.wait_3sec_cron)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)
        db.close_old_connections()

    def test_cache_locking_backend(self):
        """
        with cache locking backend
        """
        logs_count = CronJobLog.objects.all().count()
        t = threading.Thread(target=self.run_cronjob_in_thread, args=(logs_count,))
        t.daemon = True
        t.start()
        # this shouldn't get running
        sleep(0.1)  # to avoid race condition
        call(self.wait_3sec_cron)
        t.join(10)
        self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

    # TODO: this test doesn't pass - seems that second cronjob is locking file
    # however it should throw an exception that file is locked by other cronjob
    # @override_settings(
    #     DJANGO_CRON_LOCK_BACKEND='django_cron.backends.lock.file.FileLock',
    #     DJANGO_CRON_LOCKFILE_PATH=os.path.join(os.getcwd())
    # )
    # def test_file_locking_backend_in_thread(self):
    #     """
    #     with file locking backend
    #     """
    #     logs_count = CronJobLog.objects.all().count()
    #     t = threading.Thread(target=self.run_cronjob_in_thread, args=(logs_count,))
    #     t.daemon = True
    #     t.start()
    #     # this shouldn't get running
    #     sleep(1)  # to avoid race condition
    #     call(self.wait_3sec_cron)
    #     t.join(10)
    #     self.assertEqual(CronJobLog.objects.all().count(), logs_count + 1)

    def test_humanize_duration(self):
        test_subjects = (
            (timedelta(days=1, hours=1, minutes=1, seconds=1), '1 day, 1 hour, 1 minute, 1 second'),
            (timedelta(days=2), '2 days'),
            (timedelta(days=15, minutes=4), '15 days, 4 minutes'),
            (timedelta(), '< 1 second'),
        )

        for duration, humanized in test_subjects:
            self.assertEqual(
                humanize_duration(duration),
                humanized
            )


class FailureReportTests(DjangoCronTestCase):
    """
    Unit tests for the FailedRunsNotificationCronJob.
    """
    def _error_cron(self):
        call(self.error_cron, force=True)

    def _report_cron(self):
        call(self.test_failed_runs_notification_cron, force=True)

    def _error_and_report(self):
        self._error_cron()
        self._report_cron()

    def _resolve_reported_failures(self, cron_cls, failed_jobs):
        """
        Resolve the failed jobs passed to the notifier's report_failure().

        This allows us to assert the jobs passed given that failed jobs is a
        queryset which shouldn't match any instances after the notifier runs
        as it should make all log entries as having been reported.
        """
        self.reported_cls = cron_cls
        self.reported_jobs = set(failed_jobs)

    @patch.object(FailedRunsNotificationCronJob, 'report_failure')
    def test_failed_notifications(self, mock_report):
        """
        By default, the user should be notified after 10 job failures.
        """
        mock_report.side_effect = self._resolve_reported_failures

        for _ in range(9):
            self._error_and_report()
            self.assertEquals(0, mock_report.call_count)

        # The tenth error triggers the report
        self._error_and_report()
        self.assertEqual(1, mock_report.call_count)

        # The correct job class and entries should be included
        self.assertEquals(test_crons.TestErrorCronJob, self.reported_cls)
        error_logs = CronJobLog.objects.filter(
            code=test_crons.TestErrorCronJob.code
        )
        self.assertEquals(set(error_logs), self.reported_jobs)

    @patch.object(FailedRunsNotificationCronJob, 'report_failure')
    @override_settings(CRON_MIN_NUM_FAILURES=1)
    def test_settings_can_override_number_of_failures(self, mock_report):
        mock_report.side_effect = self._resolve_reported_failures
        self._error_and_report()
        self.assertEqual(1, mock_report.call_count)

    @patch.object(FailedRunsNotificationCronJob, 'report_failure')
    @override_settings(CRON_MIN_NUM_FAILURES=1)
    def test_logs_all_unreported(self, mock_report):
        mock_report.side_effect = self._resolve_reported_failures
        self._error_cron()
        self._error_and_report()
        self.assertEqual(1, mock_report.call_count)
        self.assertEqual(2, len(self.reported_jobs))

    @patch.object(FailedRunsNotificationCronJob, 'report_failure')
    @override_settings(CRON_MIN_NUM_FAILURES=1)
    def test_only_logs_failures(self, mock_report):
        mock_report.side_effect = self._resolve_reported_failures
        call(self.success_cron, force=True)
        self._error_and_report()
        self.assertEqual(
            self.reported_jobs,
            {CronJobLog.objects.get(code=test_crons.TestErrorCronJob.code)}
        )

    @patch.object(FailedRunsNotificationCronJob, 'report_failure')
    @override_settings(CRON_MIN_NUM_FAILURES=1)
    def test_only_reported_once(self, mock_report):
        mock_report.side_effect = self._resolve_reported_failures
        self._error_and_report()
        self.assertEqual(1, mock_report.call_count)

        # Calling the notifier for a second time doesn't report a second time
        self._report_cron()
        self.assertEqual(1, mock_report.call_count)

    @patch('django_cron.cron.send_mail')
    @override_settings(
        CRON_MIN_NUM_FAILURES=1,
        CRON_FAILURE_FROM_EMAIL='from@email.com',
        CRON_FAILURE_EMAIL_RECIPIENTS=['foo@bar.com', 'x@y.com'],
        FAILED_RUNS_CRONJOB_EMAIL_PREFIX='ERROR!!!'
    )
    def test_uses_send_mail(self, mock_send_mail):
        """
        Test that django_common is used to send the email notifications.
        """
        self._error_and_report()
        self.assertEquals(1, mock_send_mail.call_count)
        kwargs = mock_send_mail.call_args[1]

        self.assertIn('ERROR!!!', kwargs['subject'])
        self.assertEquals('from@email.com', kwargs['from_email'])
        self.assertEquals(
            ['foo@bar.com', 'x@y.com'], kwargs['recipient_emails']
        )
