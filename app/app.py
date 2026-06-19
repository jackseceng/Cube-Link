"""Main web application logic module"""

import hashlib
import logging
from http import HTTPStatus
from os import environ, path

import turso_mgmt as db
import url_mgmt as urls
from flask import (
    Flask,
    abort,
    make_response,
    render_template,
    request,
    send_from_directory,
)

application = Flask(__name__)

tld = environ["TLD"]
cdn = environ["CDN"]
cf_secret = environ["CF_SECRET"]

INTERNAL_REFRESH = 120


@application.route("/", methods=["POST", "GET"])
def input_url():
    """Main page process"""
    match request.method:
        case "GET":
            # Return homepage
            resp = make_response(render_template("index.html", tld=tld, cdn=cdn))
            return resp

        case "POST":
            token = request.form.get("cf-turnstile-response")
            remoteip = (
                request.headers.get("CF-Connecting-IP")
                or request.headers.get("X-Forwarded-For")
                or request.remote_addr
            )

            validation = urls.validate_turnstile(token, cf_secret, remoteip)

            if validation["success"]:
                # Valid token - process form

                # Retrieve user input from html form on index page
                # Perform syntax checks
                received_request = dict(request.form.to_dict())
                user_input = str(received_request["link"])
                error = ""
                if urls.check_url_whitespace(user_input) is False:
                    error = "whitespace"
                if urls.check_url_security(user_input) is False:
                    error = "insecure"
                if urls.check_url_reputation(user_input) is False:
                    error = "badsite"
                if len(error) != 0:
                    # If there is an error string,
                    # Return homepage with error message
                    resp = make_response(
                        render_template(
                            "index.html", errormessage=error, tld=tld, cdn=cdn
                        )
                    )
                    return resp

                custom_ext = (str
                    (received_request.get("custom_extension", ""))
                ).strip()
                if custom_ext:
                    if not urls.validate_custom_extension(custom_ext):
                        error = "customext"
                        resp = make_response(
                            render_template(
                                "index.html", errormessage=error, tld=tld, cdn=cdn
                            )
                        )
                        return resp
                    linkpath = custom_ext
                    hashsum = hashlib.sha256(linkpath.encode("utf-8")).hexdigest()
                    ciphertext, salt = urls.encrypt_url(user_input, linkpath)
                    result, message = db.insert_link(hashsum, ciphertext, salt)
                    if result is False:
                        if message == "non-unique":
                            error = "extclash"
                        else:
                            abort(HTTPStatus.INTERNAL_SERVER_ERROR)
                        resp = make_response(
                            render_template(
                                "index.html", errormessage=error, tld=tld, cdn=cdn
                            )
                        )
                        return resp
                else:
                    linkpath = urls.generate_path()
                    hashsum = hashlib.sha256(linkpath.encode("utf-8")).hexdigest()
                    ciphertext, salt = urls.encrypt_url(user_input, linkpath)

                    result, message = db.insert_link(hashsum, ciphertext, salt)
                    while result is False:
                        if message == "non-unique":
                            logging.info("Regenerating link path")
                            # Non-unique hashsum, regenerate
                            linkpath = urls.generate_path()
                            hashsum = hashlib.sha256(
                                linkpath.encode("utf-8")
                            ).hexdigest()
                            ciphertext, salt = urls.encrypt_url(user_input, linkpath)
                            result, message = db.insert_link(hashsum, ciphertext, salt)

                        elif message is not None:
                            # 500 error returned for database failure
                            abort(HTTPStatus.INTERNAL_SERVER_ERROR)
                        else:
                            # Defensive fallback for unexpected db response shape.
                            logging.error(
                                "insert_link failed with unexpected message=None"
                            )
                            abort(HTTPStatus.INTERNAL_SERVER_ERROR)
                            return None

                # Return link page with URL if successful
                resp = make_response(
                    render_template(
                        "link.html",
                        extension=str(linkpath),
                        errormessage="None",
                        tld=tld,
                        cdn=cdn,
                    )
                )
                return resp
            else:
                # Invalid token - reject submission
                error = "captchafail"
                resp = make_response(
                    render_template("index.html", errormessage=error, tld=tld, cdn=cdn)
                )
                return resp

        case _:
            # Catch all to return 500 error for any unexpected cases
            return internal_server_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    return internal_server_error(HTTPStatus.INTERNAL_SERVER_ERROR)


@application.route("/<arg>/stats")
def show_stats(arg):
    """Display statistics for a given short URL"""
    requested_path = str(arg)
    hashsum = hashlib.sha256(requested_path.encode("utf-8")).hexdigest()
    clicks, last_click = db.get_stats(hashsum)

    if clicks is not None:
        return render_template(
            "stats.html",
            extension=requested_path,
            clicks=clicks,
            last_click=last_click,
            errormessage="None",
            tld=tld,
            cdn=cdn,
        )
    else:
        abort(HTTPStatus.NOT_FOUND)


@application.route("/<arg>")
def redirect_url(arg):
    """Redirect logic for any GET requests to any URI on top of base URL"""
    # Clean arg, return 404 for unfound URL
    requested_path = str(arg)

    match requested_path:
        case "robots.txt":
            # Return robots.txt response
            resp = make_response("User-Agent: *\nDisallow: /\n")
            resp.headers["Content-Type"] = "text/plain; charset=utf-8"
            return resp
        case "favicon.ico":
            # Empty response for favicon get request
            return send_from_directory(
                path.join(application.root_path, "static"),
                "favicon.ico",
                mimetype="image/vnd.microsoft.icon",
            )
        case _:
            # Get the original URL from the database, clean it, and redirect to it
            hashsum = hashlib.sha256(requested_path.encode("utf-8")).hexdigest()
            url_bytes, salt_bytes = db.get_link(hashsum)
            if url_bytes is False:
                return page_not_found(HTTPStatus.NOT_FOUND)
            else:
                db.increment_click(hashsum)
                newlink = urls.decrypt_url(
                    url_bytes, requested_path, salt_bytes
                ).decode("utf-8")
                if not newlink.startswith("https://"):
                    return page_not_found(HTTPStatus.NOT_FOUND)
                resp = make_response(
                    render_template("redirect.html", link=newlink, tld=tld, cdn=cdn)
                )
                return resp

    return internal_server_error(HTTPStatus.INTERNAL_SERVER_ERROR)


@application.after_request
def add_security_headers(resp):
    """Add CSP headers to all responses generated"""
    cf = "challenges.cloudflare.com"

    app_origin_url = f"https://{tld}"

    # CSP sources: 'self', 'data:' (for images), and third party domains are included:
    cf_for_csp = f"https://{cf}"

    # CDN domain for web assets
    cdn_for_csp = f"https://{cdn}"

    csp_default_sources = [
        "'self'",
        cf_for_csp,
        cdn_for_csp,
    ]
    csp_img_sources = [
        "'self'",
        "data:",
        cf_for_csp,
        cdn_for_csp,
    ]
    csp_style_sources = [
        "'self'",
        cf_for_csp,
        cdn_for_csp,
    ]
    csp_script_sources = [
        "'self'",
        cf_for_csp,
        cdn_for_csp,
    ]

    final_csp_policy = f"default-src {' '.join(csp_default_sources)}; img-src {' '.join(csp_img_sources)}; style-src {' '.join(csp_style_sources)}; script-src {' '.join(csp_script_sources)};"

    # Following the OWASP cheat sheet
    resp.headers.update(
        {
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "0",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
            "Content-Security-Policy": final_csp_policy,
            "Access-Control-Allow-Origin": app_origin_url,
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "cross-site",
            "Permissions-Policy": "geolocation=(), camera=(), microphone=(), interest-cohort=()",
            "X-DNS-Prefetch-Control": "off",
        }
    )
    return resp


@application.errorhandler(HTTPStatus.NOT_FOUND)
def page_not_found(error):
    """Handles 404 Not Found errors."""
    application.logger.info("Not Found: %s", error, exc_info=True)
    resp = make_response(
        render_template("404.html",
        code=HTTPStatus.NOT_FOUND,
        tld=tld,
        cdn=cdn
        )
    )
    resp.status_code = HTTPStatus.NOT_FOUND
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@application.errorhandler(HTTPStatus.INTERNAL_SERVER_ERROR)
def internal_server_error(error):
    """Handles 500 Internal Server Errors."""
    application.logger.error("Server Error: %s", error, exc_info=True)
    resp = make_response(
        render_template(
            "500.html",
            code=HTTPStatus.INTERNAL_SERVER_ERROR,
            tld=tld,
            cdn=cdn
        )
    )
    resp.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


# Flask main function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    application.run(host="0.0.0.0", port=8080, debug=False)
