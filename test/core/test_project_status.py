from django.utils import timezone
from django.test import TestCase
from dateutil.relativedelta import relativedelta

from squad.core.models import Group, ProjectStatus


def h(n):
    """
    h(n) = n hours ago
    """
    return timezone.now() - relativedelta(hours=n)


class ProjectStatusTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        self.environment = self.project.environments.create(slug='theenvironment')
        self.suite = self.project.suites.create(slug='/')

    def create_build(self, v, datetime=None, create_test_run=True):
        build = self.project.builds.create(version=v, datetime=datetime)
        if create_test_run:
            build.test_runs.create(environment=self.environment)
        return build

    def test_status_of_first_build(self):
        build = self.create_build('1')
        status = ProjectStatus.create_or_update(build)

        self.assertEqual(build, status.build)
        self.assertIsNone(status.previous)

    def test_status_of_second_build(self):
        build = self.create_build('1')
        status1 = ProjectStatus.create_or_update(build)

        build2 = self.create_build('2')
        status2 = ProjectStatus.create_or_update(build2)
        self.assertEqual(status1, status2.previous)
        self.assertEqual(build2, status2.build)

    def test_dont_record_the_same_status_twice(self):
        build = self.create_build('1')
        status1 = ProjectStatus.create_or_update(build)
        status2 = ProjectStatus.create_or_update(build)
        self.assertEqual(status1, status2)
        self.assertEqual(1, ProjectStatus.objects.count())

    def test_wait_for_build_completion(self):
        build = self.create_build('1', datetime=h(1), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertIsNone(status)

    def test_first_build(self):
        build = self.create_build('1')
        status = ProjectStatus.create_or_update(build)
        self.assertEqual(build, status.build)

    def test_build_not_finished(self):
        build = self.create_build('2', datetime=h(4), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertIsNone(status)
        self.assertEqual(0, ProjectStatus.objects.count())

    def test_test_summary(self):
        build = self.create_build('1', datetime=h(10))
        test_run = build.test_runs.first()
        test_run.tests.create(name='foo', suite=self.suite, result=True)
        test_run.tests.create(name='bar', suite=self.suite, result=False)
        test_run.tests.create(name='baz', suite=self.suite, result=None)

        status = ProjectStatus.create_or_update(build)
        self.assertEqual(1, status.tests_pass)
        self.assertEqual(1, status.tests_fail)
        self.assertEqual(1, status.tests_skip)
        self.assertEqual(3, status.tests_total)

    def test_metrics_summary(self):
        build = self.create_build('1', datetime=h(10))
        test_run = build.test_runs.first()
        test_run.metrics.create(name='foo', suite=self.suite, result=2)
        test_run.metrics.create(name='bar', suite=self.suite, result=2)

        status = ProjectStatus.create_or_update(build)
        self.assertEqual(2.0, status.metrics_summary)

    def test_updates_data_as_new_testruns_arrive(self):
        build = self.create_build('1', datetime=h(10))
        test_run1 = build.test_runs.first()
        test_run1.tests.create(name='foo', suite=self.suite, result=True)
        ProjectStatus.create_or_update(build)

        test_run2 = build.test_runs.create(environment=self.environment)
        test_run2.tests.create(name='bar', suite=self.suite, result=True)
        test_run2.tests.create(name='baz', suite=self.suite, result=False)
        test_run2.tests.create(name='qux', suite=self.suite, result=None)
        test_run2.metrics.create(name='v1', suite=self.suite, result=5.0)
        status = ProjectStatus.create_or_update(build)

        self.assertEqual(2, status.tests_pass)
        self.assertEqual(1, status.tests_fail)
        self.assertEqual(1, status.tests_skip)
        self.assertAlmostEqual(5.0, status.metrics_summary)
