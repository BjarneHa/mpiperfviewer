__is_saved_in_current_state: bool = False


def project_updated():
    global __is_saved_in_current_state
    __is_saved_in_current_state = False


def project_saved():
    global __is_saved_in_current_state
    __is_saved_in_current_state = True


def project_saved_in_current_state():
    global __is_saved_in_current_state
    return __is_saved_in_current_state
