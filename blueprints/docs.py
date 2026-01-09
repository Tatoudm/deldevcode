
from flask import Blueprint ,render_template ,abort ,session 
from jinja2 import TemplateNotFound 
import extensions 

docs_bp =Blueprint ("docs",__name__ )

def get_header_user ():
    if "util"not in session :
        return None ,"../static/guest.png"

    user =extensions .db .utilisateurs .find_one ({"nom":session ["util"]})
    if not user :
        return None ,"../static/guest.png"

    return user ["nom"],user .get ("pdp","../static/guest.png")

@docs_bp .route ("/docs/")
@docs_bp .route ("/docs/<page>")
def serve_doc (page =None ):
    if page is None :
        page ="index"

    nom ,pdp =get_header_user ()

    try :
        return render_template (f"docs/{page }.html",nom =nom ,pdp =pdp )
    except TemplateNotFound :
        abort (404 )
