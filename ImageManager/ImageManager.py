"""
    Handles CRUD operations for firmware binary images
    Each image consists of an metadata entry and optionally an binary file
    Binary files are stored temporarily at /tmp/. This implementation assumes /tmp/ is cleaned on a regular basis
    and no effort to remove temporary files are made.
"""

import json
import logging
import os
import uuid
from flask import request
from flask import send_from_directory
from flask import Blueprint
from flask import jsonify
from minio.error import ResponseError

from .utils import *
from .DatabaseModels import *
from .SerializationModels import *
from .TenancyManager import init_tenant_context
from .app import app

image = Blueprint('image', __name__)

LOGGER = logging.getLogger('image-manager.' + __name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


@image.route('/image', methods=['GET'])
def get_all():
    try:
        init_tenant_context(request, db, minioClient)
        images = get_all_images_filter(request.args.to_dict())
        json_images = [image_schema.dump(i) for i in images]
        return make_response(jsonify(json_images), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/binary/', methods=['GET'])
def get_all_binaries():
    try:
        tenant = init_tenant_context(request, db, minioClient)
        images = minioClient.list_objects(tenant)
        image_list = [i.object_name for i in images]
        return make_response(jsonify(image_list), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/<imageid>', methods=['GET'])
def get_image(imageid):
    try:
        init_tenant_context(request, db, minioClient)
        orm_image = assert_image_exists(imageid)
        result = image_schema.dump(orm_image)
        return make_response(jsonify(result), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/<imageid>/binary/<type>', methods=['GET'])
def get_image_binary(imageid, type):
    try:
        
        tenant = init_tenant_context(request, db, minioClient)
        orm_image = assert_image_exists(imageid)
        filename = imageid
        if type == 'bin':
            filename = imageid + '.bin'
        else:
            filename = imageid + '.hex'
        print(type)

        if not orm_image.confirmed:
            raise HTTPRequestError(404, "Image does not have an binary file")
        minioClient.fget_object(tenant, filename, os.path.join('/tmp/', filename+'.hex'))
         
        print(os.path.join('/tmp/', filename))
        return send_from_directory(directory='/tmp/', filename=filename)

    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/<imageid>', methods=['DELETE'])
def delete_image(imageid):
    try:
        tenant = init_tenant_context(request, db, minioClient)
        orm_image = assert_image_exists(imageid)
        data = image_schema.dump(orm_image)

        if orm_image.confirmed:
            minioClient.remove_object(tenant, imageid + '.hex')
        db.session.delete(orm_image)
        db.session.commit()

        result ={'result': 'ok', 'removed_image': data}
        return make_response(jsonify(result), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/<imageid>/binary', methods=['DELETE'])
def delete_image_binary(imageid):
    try:
        tenant = init_tenant_context(request, db, minioClient)
        orm_image = assert_image_exists(imageid)
        minioClient.remove_object(tenant, imageid + '.hex')
        orm_image.confirmed = False
        db.session.commit()

        return make_response(jsonify({'result': 'ok'}), 200)
    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/', methods=['POST'])
def create_image():
    """ Creates and configures the given image (in json) """
    try:
        tenant = init_tenant_context(request, db, minioClient)
        image_data, json_payload = parse_json_payload(request, image_schema)
        imageid = str(uuid.uuid4())
        image_data['id'] = imageid

        orm_image = Image(**image_data)
        db.session.add(orm_image)

        try:
            db.session.commit()
        except IntegrityError as error:
            handle_consistency_exception(error)

        else:
            result = {
                "id": orm_image.id,
                "label": orm_image.label,
                "published_at": orm_image.created,
                "url": '/image/' + imageid
            }

        return make_response(jsonify(result), 201, {'location': '/image/' + imageid})

    except HTTPRequestError as e:
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


@image.route('/image/<imageid>/binary', methods=['POST'])
def upload_image(imageid):
    try:
        tenant = init_tenant_context(request, db, minioClient)
        orm_image = assert_image_exists(imageid)
        if orm_image.confirmed:
            raise HTTPRequestError(400, "Binary already exists")

        orm_image.confirmed = True
        file_data = parse_form_payload(request)

        for f in file_data:
            print(f)

        extension = file_data.filename.rsplit('.', 1)[1].lower()
        filename = imageid + '.' + extension
        file_data.seek(0)
        file_data.save(os.path.join('/tmp/', filename))
        try:
            minioClient.fput_object(tenant, filename, os.path.join('/tmp/', filename))
            orm_image.confirmed = True
            db.session.commit()
        except ResponseError as err:
            LOGGER.error(err.message)
            # TODO: Don't know how this error message is formatted, parse if necessary
            raise HTTPRequestError(400, err.message)
        except IntegrityError as error:
            handle_consistency_exception(error)

        else:
            result = {'message': 'image uploaded', 'image': imageid}

        return make_response(jsonify(result), 200)

    except HTTPRequestError as e:
        db.session.rollback()
        if isinstance(e.message, dict):
            return make_response(jsonify(e.message), e.error_code)
        else:
            return format_response(e.error_code, e.message)


app.register_blueprint(image)
