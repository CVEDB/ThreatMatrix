# This file is a part of ThreatMatrix https://github.com/khulnasoft/ThreatMatrix
# See the file 'LICENSE' for copying permission.

import logging
from abc import ABCMeta
from typing import Dict

import requests

from api_app.analyzers_manager.classes import BaseAnalyzerMixin
from api_app.analyzers_manager.exceptions import (
    AnalyzerConfigurationException,
    AnalyzerRunException,
)

logger = logging.getLogger(__name__)


class TriageMixin(BaseAnalyzerMixin, metaclass=ABCMeta):
    # using public endpoint as the default url
    url: str = "https://api.tria.ge/v0/"
    private_url: str = "https://private.tria.ge/api/v0/"
    report_url: str = "https://tria.ge/"

    endpoint: str
    _api_key_name: str
    report_type: str
    max_tries: int

    def config(self, runtime_configuration: Dict):
        super().config(runtime_configuration)
        if self.endpoint == "private":
            self.url = self.private_url

        if self.report_type not in ["overview", "complete"]:
            raise AnalyzerConfigurationException(
                "report_type must be 'overview' or 'complete' "
                f"but it is '{self.report_type}'"
            )
        self.poll_distance = 3
        self.final_report = {}
        self.response = None

    @property
    def session(self):
        if not hasattr(self, "_session"):
            session = requests.Session()
            session.headers = {
                "Authorization": f"Bearer {self._api_key_name}",
                "User-Agent": "ThreatMatrix",
            }
            self._session = session
        return self._session

    def manage_submission_response(self):
        sample_id = self.response.json().get("id", None)
        if sample_id is None:
            raise AnalyzerRunException("error sending sample")

        self.session.get(self.url + f"samples/{sample_id}/events")

        self.final_report["overview"] = self.get_overview_report(sample_id)

        if self.report_type == "complete":
            self.final_report["static_report"] = self.get_static_report(sample_id)

            self.final_report["task_report"] = {}
            for task in self.final_report["overview"]["tasks"].keys():
                status_code, task_report_json = self.get_task_report(sample_id, task)
                if status_code == 200:
                    self.final_report["task_report"][f"{task}"] = task_report_json

        analysis_id = self.final_report["overview"].get("sample", {}).get("id", "")
        if analysis_id:
            self.final_report["permalink"] = f"{self.report_url}{analysis_id}"

    def get_overview_report(self, sample_id):
        overview = self.session.get(self.url + f"samples/{sample_id}/overview.json")
        return overview.json()

    def get_static_report(self, sample_id):
        static = self.session.get(self.url + f"samples/{sample_id}/reports/static")
        return static.json()

    def get_task_report(self, sample_id, task):
        task_report = self.session.get(
            self.url + f"samples/{sample_id}/{task}/report_triage.json"
        )
        return task_report.status_code, task_report.json()
