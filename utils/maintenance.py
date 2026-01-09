
import extensions 


def is_maintenance_mode ()->bool :
    """
    Lit le flag de maintenance dans la collection site_settings.
    Document : { _id: "maintenance", enabled: bool }
    """
    try :
        settings_col =extensions .db .site_settings 
        doc =settings_col .find_one ({"_id":"maintenance"})
        return bool (doc and doc .get ("enabled",False ))
    except Exception :
        return False 
