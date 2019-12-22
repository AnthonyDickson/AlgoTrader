def format_net_value(value: float) -> str:
    formatted_value = f"{abs(value):.2f}"

    if value < 0:
        formatted_value = f"({formatted_value})"
    else:
        formatted_value = f" {formatted_value} "

    return formatted_value
