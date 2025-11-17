# utils/pdf_utils.py
from django.template.loader import render_to_string
from django.conf import settings
from io import BytesIO
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

def intervention_to_pdf_buffer(intervention, logo_url=None):
    """
    Render the HTML template and return a BytesIO buffer containing the PDF.
    """
    # Test WeasyPrint import with detailed error logging
    try:
        from weasyprint import HTML, CSS, __version__
        logger.info(f"WeasyPrint successfully imported. Version: {__version__}")
    except ImportError as e:
        logger.error(f"WeasyPrint import failed: {str(e)}")
        logger.error("Please ensure system dependencies are installed:")
        logger.error("libpango, libcairo, libgdk-pixbuf, etc.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error importing WeasyPrint: {str(e)}")
        raise

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

    try:
        html_string = render_to_string('reports/intervention_report.html', context)
        logger.info("HTML template rendered successfully")
    except Exception as e:
        logger.error(f"Template rendering failed: {str(e)}")
        raise

    # Generate PDF
    pdf_io = BytesIO()
    
    try:
        # Use base_url to allow WeasyPrint to access local files (like logos)
        # For Railway/production, use STATIC_URL if STATIC_ROOT is not accessible
        if settings.DEBUG:
            base_url = settings.STATIC_ROOT or str(settings.BASE_DIR)
        else:
            # In production, use the full static URL or a file path if mounted
            base_url = getattr(settings, 'STATIC_ROOT', None) or str(settings.BASE_DIR)
        
        logger.info(f"Using base_url: {base_url}")
        
        # Create HTML object
        html_doc = HTML(string=html_string, base_url=base_url)
        logger.info("HTML object created successfully")
        
        # Write PDF
        html_doc.write_pdf(pdf_io)
        logger.info("PDF generated successfully")
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    
    pdf_io.seek(0)
    return pdf_io


def test_weasyprint_dependencies():
    """
    Diagnostic function to test WeasyPrint dependencies.
    Call this from a management command or view to debug issues.
    """
    results = {}
    
    # Test WeasyPrint import
    try:
        from weasyprint import HTML, __version__
        results['weasyprint_import'] = f"Success (v{__version__})"
    except ImportError as e:
        results['weasyprint_import'] = f"Failed: {str(e)}"
        return results
    except Exception as e:
        results['weasyprint_import'] = f"Error: {str(e)}"
        return results
    
    # Test cairocffi (required by WeasyPrint)
    try:
        import cairocffi
        results['cairocffi'] = f"Success (v{cairocffi.version})"
    except ImportError as e:
        results['cairocffi'] = f"Failed: {str(e)}"
    except Exception as e:
        results['cairocffi'] = f"Error: {str(e)}"
    
    # Test Pango (required for text layout)
    try:
        import cairocffi
        cairocffi.install_as_pycairo()
        from weasyprint.text.ffi import ffi, pango
        results['pango'] = "Success"
    except Exception as e:
        results['pango'] = f"Failed: {str(e)}"
    
    # Test simple PDF generation
    try:
        test_html = "<html><body><h1>Test</h1></body></html>"
        test_pdf = BytesIO()
        HTML(string=test_html).write_pdf(test_pdf)
        results['pdf_generation'] = "Success"
    except Exception as e:
        results['pdf_generation'] = f"Failed: {str(e)}"
    
    return results