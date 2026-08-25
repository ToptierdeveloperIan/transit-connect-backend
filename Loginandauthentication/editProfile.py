from Loginandauthentication.models import CustomUser


def changeFirstName(user_id, firstName):
    try:
        updated = CustomUser.objects.filter(id=user_id).update(first_name=firstName)
        if updated == 0:
            return "No user found with that ID."
        return "First name updated successfully."
    except Exception as e:
        return f"Error: {e}"
def changeLastName(user_id, lastName):
    try:
        updated = CustomUser.objects.filter(id=user_id).update(second_name=lastName)
        if updated == 0:
            return "No user found with that ID."
        return "First name updated successfully."
    except Exception as e:
        return f"Error: {e}"
def changeEmail(user_id, email):
    try:
        updated = CustomUser.objects.filter(id=user_id).update(email=email)
        if updated == 0:
            return "No user found with that ID."
        return "First name updated successfully."
    except Exception as e:
        return f"Error: {e}"
def changePhone(user_id, phone):
    try:
        updated = CustomUser.objects.filter(id=user_id).update(phone=phone)
        if updated == 0:
            return "No user found with that ID."
        return "First name updated successfully."
    except Exception as e:
        return f"Error: {e}"
