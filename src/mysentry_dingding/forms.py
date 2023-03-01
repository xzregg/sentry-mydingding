# coding: utf-8

from django import forms


class DingDingOptionsForm(forms.Form):
    access_token = forms.CharField(
            max_length=255,
            help_text='DingTalk robot access_token'
    )

    gitlab_project_name = forms.CharField(
            max_length=255,
            help_text=u'Gitlab 项目名，补全group，类似 backend/cashier_v4'
    )

    gitlab_url = forms.CharField(
            max_length=255,
            help_text=u'Gitlab address,类似 https://gitlab.xxxx.com/shixiang-sass/backend/项目名/blame/'
    )

    deploy_path = forms.CharField(
            max_length=255,
            help_text=u'项目部署绝对路径,如 /app'
    )
    gitlab_private_token = forms.CharField(
            max_length=255,
            help_text=u'Gitlab 访问 token(private_token)'
    )
    branch = forms.CharField(
            max_length=255,
            help_text=u'分支名:如 master'
    )
    gitlab_contact = forms.CharField(
            widget=forms.Textarea,
            help_text=u'联系人,格式: 名字 手机号 一行一个'
    )