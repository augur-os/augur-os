use AppleScript version "2.4"
use scripting additions

on run
    set homePath to (path to home folder as text)
    set posixHome to POSIX path of (path to home folder)
    set requestPath to posixHome & "Projects/augur-data/operations/state/ipc/bridge_request.json"
    set responsePath to posixHome & "Projects/augur-data/operations/state/ipc/bridge_response.json"
    
    try
        -- Read Request
        set shellCmd to "/usr/bin/python3 -c \"import json; data=json.load(open('" & requestPath & "')); print(data['prompt']); print('---SPLIT---'); print(data['app_name'])\""
        set rawOutput to do shell script shellCmd
        
        set AppleScript's text item delimiters to "---SPLIT---"
        set thePrompt to text item 1 of rawOutput
        set theApp to text item 2 of rawOutput
        
        -- Trim newlines if any (python print adds newline)
        -- Actually python print adds newline at end.
        -- Let's strip it in python or here.
        -- Better: json dump robustly.
        
        -- Refined read:
        set thePrompt to do shell script "/usr/bin/python3 -c \"import json, sys; sys.stdout.write(json.load(open('" & requestPath & "'))['prompt'])\""
        set theApp to do shell script "/usr/bin/python3 -c \"import json, sys; sys.stdout.write(json.load(open('" & requestPath & "'))['app_name'])\""
        
        -- Execute Paste
        set the clipboard to thePrompt
        
        tell application theApp to activate
        delay 0.5
        
        try
            tell application "System Events"
                tell process theApp
                    if theApp contains "Claude" then
                        -- Claude Desktop: new conversation, paste, submit
                        delay 0.5
                        keystroke "n" using {command down}
                        delay 2.0
                        keystroke "v" using {command down}
                        delay 0.5
                        keystroke return
                    else if theApp contains "Cursor" then
                        keystroke "l" using {command down}
                        delay 0.5
                        keystroke "v" using {command down}
                        delay 0.3
                        keystroke return
                    else
                        try
                            tell menu bar 1
                                tell menu "View"
                                    click menu item "Command Palette..."
                                end tell
                            end tell
                        on error
                            key code 122
                        end try
                        delay 0.2
                        keystroke "Chat: Focus Input"
                        delay 0.4
                        keystroke return
                        delay 0.4
                        keystroke "v" using {command down}
                        delay 0.3
                        keystroke return
                    end if
                end tell
            end tell
            
            -- Write Success Response
            do shell script "/usr/bin/python3 -c \"import json; json.dump({'success': True, 'message': 'Pasted to ' + '" & theApp & "'}, open('" & responsePath & "','w'))\""
            
        on error errMsg
            if errMsg contains "not allowed" or errMsg contains "System Events" then
                -- Fallback: clipboard is set, IDE is open, just let user know
                do shell script "/usr/bin/python3 -c \"import json; json.dump({'success': True, 'message': '" & theApp & " focused. Please press Cmd+V to paste manually (Accessibility permission required for auto-paste).'}, open('" & responsePath & "','w'))\""
            else
                error errMsg
            end if
        end try
        
    on error errMsg
        -- Write Error Response
        do shell script "/usr/bin/python3 -c \"import json; json.dump({'success': False, 'error': '" & errMsg & "'}, open('" & responsePath & "','w'))\""
    end try
end run
