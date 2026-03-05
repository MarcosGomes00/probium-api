def success(data=None, message="success"):

    return {
        "status": "success",
        "message": message,
        "data": data
    }


def error(message="error", code=400):

    return {
        "status": "error",
        "message": message,
        "code": code
    }
