# Copyright 2015 Internap.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import wraps
import logging

from flask import make_response, request, Response
from werkzeug.routing import BaseConverter

from netman.api.serializer import SWJsonify
from netman.core.objects.exceptions import UnknownResource, Conflict


def to_response(fn):
    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
            if isinstance(result, Response):
                return result
            else:
                code, data = result
                if data is not None:
                    response = SWJsonify(data)
                    response.status_code = code
                else:
                    response = make_response("", code)
        except (BadRequest, ValueError) as e:
            response = exception_to_response(e, 400)
        except UnknownResource as e:
            response = exception_to_response(e, 404)
        except Conflict as e:
            response = exception_to_response(e, 409)
        except Exception as e:
            logging.exception(e)
            response = exception_to_response(e, 500)

        self.logger.info("Responding {} : {}".format(response.status_code, response.data))
        return response

    return wrapper


def exception_to_response(exception, code):
    data = {'error': str(exception)}
    if data['error'] == "":
        data['error'] = "Unexpected error: {}.{}".format(exception.__module__, exception.__class__.__name__)
    if "Netman-Verbose-Errors" in request.headers:
        if hasattr(exception, "__module__"):
            data["error-module"] = exception.__module__
        data["error-class"] = exception.__class__.__name__

    response = SWJsonify(data)
    response.status_code = code

    return response


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


class BadRequest(Exception):
    pass


class MultiContext(object):
    def __init__(self, switch_api, parameters,  *contexts):
        self.context_instances = []
        for context in contexts:
            obj = context(switch_api)
            obj.process(parameters)
            self.context_instances.append(obj)

        self.parameters = parameters

    def __enter__(self):
        return [(obj.__enter__()) for obj in self.context_instances]

    def __exit__(self, type_, value, traceback):
        for context in self.context_instances:
            context.__exit__(type_, value, traceback)