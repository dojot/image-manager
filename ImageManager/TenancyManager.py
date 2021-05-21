import base64
import json
from sqlalchemy.sql import exists, select, text
from minio.error import (
    ResponseError, BucketAlreadyOwnedByYou, BucketAlreadyExists)
from .utils import HTTPRequestError


def decode_base64(data):
    """Decode base64, padding being optional.

    :param data: Base64 data as an ASCII byte string
    :returns: The decoded byte string.

    """
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    return base64.decodebytes(data.encode()).decode()


def get_allowed_service(token):
    """
        Parses the authorization token, returning the service to be used when
        configuring the FIWARE backend

        :param token: JWT token to be parsed
        :returns: Fiware-service to be used on API calls
        :raises ValueError: for invalid token received
    """
    if not token or len(token) == 0:
        raise ValueError("Invalid authentication token")

    payload = token.split('.')[1]
    try:
        data = json.loads(decode_base64(payload))
        # to ensure backward compatibility
        if ('service' in data):
            return data['service']
        elif ('iss' in data):
            iss = data['iss']
            return iss[iss.rindex('/') + 1:]
        else:
            return None
    except Exception as ex:
        raise ValueError(
            "Invalid authentication token payload - not json object", ex)


def create_tenant(tenant, db):
    db.session.execute("create schema \"%s\";" % tenant)


def switch_tenant(tenant, db):
    db.session.execute("SET search_path TO %s" % tenant)
    db.session.commit()


def init_tenant(tenant, db, minioClient):
    # Check if Postgres schema exists
    query = exists(select([text("schema_name")])
                   .select_from(text("information_schema.schemata"))
                   .where(text("schema_name = '%s'" % tenant)))
    tenant_exists = db.session.query(query).scalar()

    if not tenant_exists:
        create_tenant(tenant, db)
        switch_tenant(tenant, db)
        db.create_all()
        # install_triggers(db)
    else:
        switch_tenant(tenant, db)

    # Check if Minio Bucket exists
    try:
        # TODO Set bucket location
        minioClient.make_bucket(tenant)
    except BucketAlreadyOwnedByYou as err:
        pass
    except BucketAlreadyExists as err:
        pass
    except ResponseError as err:
        raise


def init_tenant_context(request, db, minioClient):
    try:
        token = request.headers['authorization']
    except KeyError:
        raise HTTPRequestError(401, "No authorization token has been supplied")

    tenant = get_allowed_service(token)
    init_tenant(tenant, db, minioClient)
    return tenant
