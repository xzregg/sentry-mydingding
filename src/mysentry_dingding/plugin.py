# coding: utf-8

import json

import requests
import six
from sentry.plugins.bases.notify import NotificationPlugin
from sentry import features
from sentry.models import Event
import sentry_dingding
from .forms import DingDingOptionsForm
import gitlab


def get_git_track_msg_author_info(git_url, private_token, project_name_with_namespace, filename, lineno, branch='master'):
    try:
        gl = gitlab.Gitlab(url=git_url, private_token=private_token)
        project = gl.projects.get(project_name_with_namespace)
        blames = project.files.blame(filename, branch)
        tlc = 0
        for item in blames:
            commit, lines = item.get('commit', {}), item.get('lines', [])
            tlc += len(lines)
            if tlc >= lineno:
                return commit
        return {}
    except gitlab.exceptions.GitlabListError as e:
        return {}
    except Exception as e:
        return {}


DingTalk_API = "https://oapi.dingtalk.com/robot/send?access_token={token}"


class DingDingPlugin(NotificationPlugin):
    """
    Sentry plugin to send error counts to DingDing.
    """
    author = 'ansheng'
    author_url = 'https://github.com/anshengme/sentry-dingding'
    version = sentry_dingding.VERSION
    description = 'Send error counts to DingDing.'
    resource_links = [
            ('Source', 'https://github.com/anshengme/sentry-dingding'),
            ('Bug Tracker', 'https://github.com/anshengme/sentry-dingding/issues'),
            ('README', 'https://github.com/anshengme/sentry-dingding/blob/master/README.md'),
    ]

    slug = 'DingDing'
    title = 'DingDing'
    conf_key = slug
    conf_title = title
    project_conf_form = DingDingOptionsForm

    def is_configured(self, project):
        """
        Check if plugin is configured.
        """
        return bool(self.get_option('access_token', project))

    def notify_users(self, group, event, *args, **kwargs):
        self.post_process(group, event, *args, **kwargs)

    def post_process(self, group, event, *args, **kwargs):
        """
        Process error.
        """
        if not self.is_configured(group.project):
            return

        if group.is_ignored():
            return

        access_token = self.get_option('access_token', group.project)
        gitlab_url = self.get_option('gitlab_url', group.project) or ''
        gitlab_project_name = self.get_option('gitlab_project_name', group.project) or ''
        gitlab_private_token = self.get_option('gitlab_private_token', group.project) or ''
        deploy_path = self.get_option('deploy_path', group.project) or ''
        branch = self.get_option('branch', group.project) or ''
        gitlab_contact = self.get_option('gitlab_contact', group.project) or ''
        contact_map = dict([line.split() for line in gitlab_contact.split('\n') if line])
        at_list = []
        send_url = DingTalk_API.format(token=access_token)
        title = u"New alert from {}".format(event.project.slug)
        event_data = dict(event.data)
        values = event_data.get('exception', {}).get('values')
        gitlab_url = gitlab_url.strip("/")
        git_msg = ''
        if values:
            stacktrace = values[-1]
            stacktrace = stacktrace.get('stacktrace')
            if stacktrace:
                frames = stacktrace['frames']
                for last_frame in frames[::-1]:
                    in_app = last_frame.get('in_app')
                    extra = event_data.get('extra', {})
                    git_msg = extra.get('git_msg', '').strip("'")
                    rid = extra.get('rid', '').strip("'") or extra.get('task_id', '').strip("'")

                    lineno = last_frame.get('lineno')
                    abs_path = last_frame.get('abs_path', '')
                    abs_path = abs_path.replace('\\', '/')
                    in_app = in_app or (deploy_path and abs_path.startswith(deploy_path))
                    if in_app:
                        file_path = abs_path.split(deploy_path, 1)[-1]
                        filename = file_path.strip('/')
                        git_commit = get_git_track_msg_author_info(gitlab_url, gitlab_private_token, gitlab_project_name, filename, lineno, branch=branch)
                        if git_commit:
                            committer_name = git_commit.get('committer_name').strip()
                            at_name = contact_map.get(committer_name, '')
                            git_repo_url = '%s/%s/blame/%s/%s#L%s' % (gitlab_url, gitlab_project_name, branch, filename, lineno)
                            git_msg = '%s %s [gitlab](%s)' % (filename, lineno, git_repo_url)
                            # https://gitlab.base.packertec.com/shixiang-sass/backend/cashier_v4/blame/master/sdks/alipay.py#L14
                            git_msg = u'\n\n %s %s @%s %s' % (git_msg, git_commit.get('message').strip(), at_name or committer_name, rid)
                            if at_name:
                                at_list.append(at_name)
                            break

        data = {
                "msgtype" : "markdown",
                "markdown": {
                        "title": title,
                        "text" : u"#### {title} \n > {message} [sentry]({sentry_url}) {git_msg}".format(
                                title=title,
                                message=event.message,
                                sentry_url=u"{}events/{}/".format(group.get_absolute_url(), event.id or event.event_id or 'latest'),
                                git_msg=git_msg,
                        )
                }
        }
        if at_list:
            data["at"] = {"atMobiles": at_list}
        requests.post(
                url=send_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(data).encode("utf-8")
        )

    def get_group_data(self, group, event, triggering_rules):
        data = {
                'id'              : six.text_type(group.id),
                'project'         : group.project.slug,
                'project_name'    : group.project.name,
                'project_slug'    : group.project.slug,
                'logger'          : event.get_tag('logger'),
                'level'           : event.get_tag('level'),
                'culprit'         : group.culprit,
                'message'         : event.real_message,
                'url'             : group.get_absolute_url(params={'referrer': 'webhooks_plugin'}),
                'triggering_rules': triggering_rules,
        }
        data['event'] = dict(event.data or {})
        data['event']['tags'] = event.tags
        data['event']['event_id'] = event.event_id
        if features.has('organizations:legacy-event-id', group.project.organization):
            try:
                data['event']['id'] = Event.objects.filter(
                        project_id=event.project_id,
                        event_id=event.event_id,
                ).values_list('id', flat=True).get()
            except Event.DoesNotExist:
                data['event']['id'] = None
        return data
