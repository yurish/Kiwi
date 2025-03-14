# -*- coding: utf-8 -*-
import requests
from requests.auth import HTTPBasicAuth

from tcms.core.contrib.linkreference.models import LinkReference
from tcms.issuetracker.base import IssueTrackerType


class BitBucketAPI:
    """
    BitBucket API interaction class.

    :meta private:
    """

    def __init__(self, base_url=None, api_username=None, api_password=None):
        api_version = "2.0"
        self.endpoint_url = self._construct_endpoint_url(api_version, base_url)
        self.headers = {
            "Accept": "application/json",
            "Content-type": "application/json",
        }
        self.auth = HTTPBasicAuth(api_username, api_password)

    def create_issue(self, data):
        url = f"{self.endpoint_url}/issues"
        return self._request(
            "POST", url, headers=self.headers, auth=self.auth, json=data
        )

    def get_issue(self, issue_id):
        url = f"{self.endpoint_url}/issues/{issue_id}"
        return self._request("GET", url, headers=self.headers, auth=self.auth)

    def update_issue(self, issue_id, data):
        url = f"{self.endpoint_url}/issues/{issue_id}/changes"
        return self._request(
            "POST", url, headers=self.headers, auth=self.auth, json=data
        )

    def add_comment(self, issue_id, comment):
        url = f"{self.endpoint_url}/issues/{issue_id}/comments/"
        return self._request(
            "POST", url, headers=self.headers, auth=self.auth, json=comment
        )

    def get_comments(self, issue_id):
        url = f"{self.endpoint_url}/issues/{issue_id}/comments?sort=-updated_on"
        return self._request("GET", url, headers=self.headers, auth=self.auth)

    def delete_comment(self, issue_id, comment_id):
        url = f"{self.endpoint_url}/issues/{issue_id}/comments/{comment_id}"
        return self._request("DELETE", url, headers=self.headers, auth=self.auth)

    @staticmethod
    def _request(method, url, **kwargs):
        if method == "DELETE":
            return requests.request(method, url, timeout=30, **kwargs)
        return requests.request(method, url, timeout=30, **kwargs).json()

    @staticmethod
    def _construct_endpoint_url(api_version, url):
        splitted_url = url.replace("https://", "").split("/")
        base_url = "https://api.bitbucket.org"
        workspace = splitted_url[1]
        repository = splitted_url[2]
        endpoint_url = f"{base_url}/{api_version}/repositories/{workspace}/{repository}"
        return endpoint_url


class BitBucket(IssueTrackerType):
    """
    Support for BitBucket. Requires:

    :base_url: Repository URL - e.g. https://bitbucket.org/{workspace}/{repository}
    :api_username: BitBucket Username
    :api_password: BitBucket App Password - needs Issues: Read & write permission.

    .. note::

        You can leave the ``api_url`` field blank because the integration
        code doesn't use it!

    .. warning::

        ``api_username`` is your BitBucket username, which you use to log in.

    .. note::

        ``api_password`` is "App Password" created in BitBucket.
        Here is a guide about creating and using an "App Password";
        https://support.atlassian.com/bitbucket-cloud/docs/app-passwords/
    """

    def _rpc_connection(self):
        (api_username, api_password) = self.rpc_credentials

        return BitBucketAPI(
            self.bug_system.base_url,
            api_username=api_username,
            api_password=api_password,
        )

    def is_adding_testcase_to_issue_disabled(self):
        (api_username, api_password) = self.rpc_credentials

        return not (self.bug_system.base_url and api_username and api_password)

    def _report_issue(self, execution, user):
        """
        BitBucket creates the Issue with Title and Description
        """

        data = {
            "title": f"Failed test: {execution.case.summary}",
            "kind": "bug",
            "priority": "major",
            "content": {
                "raw": self._report_comment(execution, user).replace("\n", "\r\n")
            },
        }

        try:
            issue = self.rpc.create_issue(data)

            issue_url = f"{self.bug_system.base_url}/issues/{issue['id']}"
            # add a link reference that will be shown in the UI
            LinkReference.objects.get_or_create(
                execution=execution,
                url=issue_url,
                is_defect=True,
            )

            return (issue, issue_url)
        except Exception:  # pylint: disable=broad-except
            # something above didn't work so return a link for manually
            # entering issue details with info pre-filled
            url = self.bug_system.base_url
            if not url.endswith("/"):
                url += "/"

            return (None, url + "issues/new")

    def post_comment(self, execution, bug_id):
        comment_body = {"content": {"raw": self.text(execution).replace("\n", "\n\n")}}
        self.rpc.add_comment(bug_id, comment_body)

    def details(self, url):
        """
        Return issue details from BitBucket
        """
        issue = self.rpc.get_issue(self.bug_id_from_url(url))
        return {
            "id": issue["id"],
            "description": issue["content"]["raw"],
            "status": issue["state"],
            "title": issue["title"],
            "url": url,
        }
