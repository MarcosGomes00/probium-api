from flask import jsonify


def register_error_handlers(app):

    @app.errorhandler(404)
    def not_found(error):

        return jsonify({
            "status": "error",
            "message": "route not found"
        }), 404


    @app.errorhandler(500)
    def internal_error(error):

        return jsonify({
            "status": "error",
            "message": "internal server error"
        }), 500