import os
import re

files_to_fix = [
    r'c:\Projects\Personal\2026\Full\Eglises\church\views.py',
    r'c:\Projects\Personal\2026\Full\Eglises\church\view_helpers.py',
    r'c:\Projects\Personal\2026\Full\Eglises\church\superadmin_views.py',
    r'c:\Projects\Personal\2026\Full\Eglises\church\public_views.py',
    r'c:\Projects\Personal\2026\Full\Eglises\church\notification_views.py',
]

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    original_lines = lines.copy()
    
    # Needs logging import
    has_logging = any('import logging' in line for line in lines)
    if not has_logging:
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, 'import logging\n')
                break
                
    has_logger = any('logger = logging.getLogger' in line for line in lines)
    if not has_logger:
        # Find last import
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i
        lines.insert(last_import_idx + 1, '\nlogger = logging.getLogger(__name__)\n')
        
    # Replace logic
    for i in range(len(lines)):
        if "except Exception:" in lines[i]:
            # find context by looking back
            context = "Unknown operation failed."
            j = i - 1
            while j >= max(0, i - 15):
                if 'action=' in lines[j] or 'action =' in lines[j]:
                    m = re.search(r'action\s*=\s*["\']([^"\']+)["\']', lines[j])
                    if m:
                        context = f"Failed to log audit for action '{m.group(1)}'"
                        break
                elif '_send_invite_email' in lines[j]:
                    context = "Failed to send invite email"
                    break
                elif 'callback()' in lines[j]:
                    context = "Failed to execute after-commit callback"
                    break
                j -= 1
            
            # Now replace the next line if it is "pass"
            indent = lines[i].split("except")[0] + "    "
            if i + 1 < len(lines) and "pass\n" in lines[i+1]:
                lines[i+1] = f'{indent}logger.error("{context}", exc_info=True)\n'
            elif i + 2 < len(lines) and "email_error = True" in lines[i+1]:
                # Insert the log before email_error = True
                lines.insert(i+1, f'{indent}logger.error("{context}", exc_info=True)\n')

    if lines != original_lines:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Updated {filepath}")
