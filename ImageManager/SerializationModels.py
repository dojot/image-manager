# object to json sweetness
import json
from marshmallow import Schema, fields, post_dump
from marshmallow import ValidationError
from .utils import HTTPRequestError
import logging

LOGGER = logging.getLogger('image-manager.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class ImageSchema(Schema):
    id = fields.String(dump_only=True)
    label = fields.Str(required=True)
    created = fields.DateTime(dump_only=True)
    updated = fields.DateTime(dump_only=True)

    fw_version = fields.String(required=True)
    confirmed = fields.Bool(required=False)

    @post_dump
    def remove_null_values(self, data):
        return {key: value for key, value in data.items() if value is not None}


image_schema = ImageSchema()

ALLOWED_EXTENSIONS = set(['hex', 'bin'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_form_payload(request):
    # Validate http header info
    content_type = request.headers.get('Content-Type')
    if (content_type is None) or ("multipart/form-data" not in content_type):
        raise HTTPRequestError(400, "Payload must be valid multipart/form-data, not: {}".format(
            request.headers.get('Content-Type')))

    if not request.files:
        raise HTTPRequestError(400, "Payload must contain a file")

    # Validate incoming file
    if 'image' not in request.files:
        raise HTTPRequestError(400, "File form does not have an image field")
    file_data = request.files['image']
    if file_data.filename == '':
        raise HTTPRequestError(400, "Filename empty")

    if not (file_data and allowed_file(file_data.filename)):
        LOGGER.debug("file_data: {}, filename: {}".format(file_data, file_data.filename))
        raise HTTPRequestError(400, "Invalid File")

    return file_data


def parse_json_payload(request, schema):
    try:
        content_type = request.headers.get('Content-Type')
        if (content_type is None) or (content_type != "application/json"):
            raise HTTPRequestError(400, "Payload must be valid JSON, and Content-Type set accordingly")
        json_payload = json.loads(request.data.decode('utf-8'))
    except ValueError:
        raise HTTPRequestError(400, "Payload must be valid JSON, and Content-Type set accordingly")

    try:
        print(json_payload)
        data = schema.load(json_payload)
        print(data)
    except ValidationError as error:
        results = {'message': 'failed to parse input', 'errors': error.messages}
        raise HTTPRequestError(400, results)
    return data, json_payload
