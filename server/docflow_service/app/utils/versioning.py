def create_new_version(old_doc, new_content, current_user):
    return Document(
        title=old_doc.title,
        content=new_content,
        version=old_doc.version + 1,
        created_by_id=current_user.id,
        parent_id=old_doc.id,
        category=old_doc.category,
        tags=old_doc.tags.copy()
    )