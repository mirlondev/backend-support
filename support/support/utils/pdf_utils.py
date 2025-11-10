# utils/pdf_utils.py
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML, CSS
from io import BytesIO
from datetime import datetime
import os

def intervention_to_pdf_buffer(intervention, logo_url=None):
    """
    Render the HTML template and return a BytesIO buffer containing the PDF.
    """
    # Build context (safe getattr usage)
    ticket = getattr(intervention, 'ticket', None)
    client = getattr(ticket, 'client', None)
    technician = getattr(intervention, 'technician', None)
    tech_user = getattr(technician, 'user', None) if technician else None

    # Parse materials if stored as text "name:qty:cost\n..."
    materials_raw = getattr(intervention, 'materials_used', '') or ''
    materials = []
    for line in materials_raw.splitlines():
        if not line.strip(): 
            continue
        parts = [p.strip() for p in line.split(':')]
        materials.append({
            'name': parts[0] if len(parts) > 0 else 'Unnamed Material',
            'qty': parts[1] if len(parts) > 1 else 'N/A',
            'cost': parts[2] if len(parts) > 2 else '0.00'
        })

    # Format dates properly
    intervention_date = getattr(intervention, 'intervention_date', None)
    if intervention_date:
        intervention_date = intervention_date.strftime('%Y-%m-%d')
    
    start_time = getattr(intervention, 'start_time', None)
    if start_time:
        start_time = start_time.strftime('%H:%M')
    
    end_time = getattr(intervention, 'end_time', None)
    if end_time:
        end_time = end_time.strftime('%H:%M')

    # Get status with proper display
    status = getattr(intervention, 'status', 'unknown')
    status_display = getattr(intervention, 'get_status_display', None)
    if status_display and callable(status_display):
        status_display = status_display()
    else:
        status_display = status.capitalize()

    context = {
        'logo_url': logo_url or '',
        'now': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'intervention': intervention,
        'intervention_id': getattr(intervention, 'id', 'N/A'),
        'intervention_date': intervention_date,
        'start_time': start_time,
        'end_time': end_time,
        'hours_worked': getattr(intervention, 'hours_worked', '0'),
        'travel_time': getattr(intervention, 'travel_time', '0'),
        'transport_cost': getattr(intervention, 'transport_cost', '0.00'),
        'additional_costs': getattr(intervention, 'additional_costs', '0.00'),
        'total_cost': getattr(intervention, 'total_cost', '0.00'),
        'report': getattr(intervention, 'report', 'No details provided.'),
        'materials': materials,
        'client_username': getattr(getattr(client, 'user', None), 'username', 'N/A') if client else 'N/A',
        'client_name': getattr(client, 'company', None) or 
                      (f"{getattr(getattr(client, 'user', None), 'first_name', '')} "
                       f"{getattr(getattr(client, 'user', None), 'last_name', '')}".strip() 
                       if client and getattr(client, 'user', None) else 'N/A'),
        'client_address': getattr(client, 'address', '') or '',
        'client_contact': getattr(client, 'phone', '') or 
                         (getattr(getattr(client, 'user', None), 'email', '') if client else ''),
        'ticket_id': getattr(ticket, 'id', 'N/A') if ticket else 'N/A',
        'tech_name': (f"{getattr(tech_user, 'first_name', '')} {getattr(tech_user, 'last_name', '')}".strip() 
                     if tech_user else 'Unassigned'),
        'status_display': status_display
    }

    html_string = render_to_string('reports/intervention_report.html', context)

    # Generate PDF
    pdf_io = BytesIO()
    
    # Use base_url to allow WeasyPrint to access local files (like logos)
    base_url = settings.STATIC_ROOT or settings.BASE_DIR
    HTML(string=html_string, base_url=base_url).write_pdf(pdf_io)
    
    pdf_io.seek(0)
    return pdf_io