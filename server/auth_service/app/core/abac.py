def has_service_access(user_attrs: dict, service: str, permission: str) -> bool:
   
    services = user_attrs.get("services", {})
    service_perms = services.get(service, {})
    return service_perms.get(permission, False)


@app.get("/storage/files")
def get_files(current_user=Depends(get_current_user)):
    if not has_service_access(current_user.attributes, "storage", "read"):
        raise HTTPException(403, f"Access denied to 'storage' (required: read)")
    return storage_client.list_files()