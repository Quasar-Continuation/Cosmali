def create_pagination_info(page, per_page, total):
    """Create pagination information"""
    pages = (total + per_page - 1) // per_page  # Ceiling division
    has_prev = page > 1
    has_next = page < pages

    return {
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "total": total,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": page - 1 if has_prev else None,
        "next_page": page + 1 if has_next else None,
    }
