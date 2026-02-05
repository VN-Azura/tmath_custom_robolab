# Import and Export API
import orjson

from ninja import NinjaAPI, ModelSchema, Schema
from ninja.errors import HttpError
from ninja.renderers import BaseRenderer

from judge.models import Problem


class ORJSONRenderer(BaseRenderer):
    media_type = "application/json"

    def render(self, request, data, *, response_status):
        return orjson.dumps(data)


api = NinjaAPI(renderer=ORJSONRenderer(), title="TMath Sync API", version="1.0.0")


class ErrorSchema(Schema):
    detail: str


class ProblemExportData(ModelSchema):
    class Meta:
        model = Problem
        fields = [
            'code', 'name', 'description',
            'types', 'group', 'classes',
            'time_limit', 'memory_limit', 'points', 'partial',
            'allowed_languages', 'is_public', 'approved',
        ]


@api.get("/problem/{problem_code}/", response=ProblemExportData)
def export_problem(request, problem_code: str):
    try:
        problem = Problem.objects.get(code=problem_code)
    except Problem.DoesNotExist:
        raise HttpError(404, "Problem not found")
    return problem
