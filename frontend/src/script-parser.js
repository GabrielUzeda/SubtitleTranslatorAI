// Enhanced script parser for main.sh
// This module provides intelligent parsing of shell scripts to extract argument information

class ScriptParser {
    constructor(scriptContent) {
        this.content = scriptContent;
        this.lines = scriptContent.split('\n');
    }

    // Main parsing function
    parseArguments() {
        const args = [];
        
        // Parse from usage function
        const usageArgs = this.parseUsageFunction();
        args.push(...usageArgs);
        
        // Parse from getopts/case statements
        const caseArgs = this.parseCaseStatements();
        args.push(...caseArgs);
        
        // Parse from variable assignments and comments
        const commentArgs = this.parseCommentedArguments();
        args.push(...commentArgs);
        
        // Detect file/directory inputs from script logic
        const fileArgs = this.detectFileArguments();
        args.push(...fileArgs);
        
        // Remove duplicates and merge information
        return this.mergeDuplicates(args);
    }

    // Parse the usage() function
    parseUsageFunction() {
        const args = [];
        const usageMatch = this.content.match(/usage\(\)\s*{\s*([\s\S]*?)\s*}/);
        
        if (!usageMatch) return args;
        
        const usageContent = usageMatch[1];
        
        // Extract option patterns like "-s, --select"
        const optionRegex = /(-[a-zA-Z]|--[a-zA-Z][a-zA-Z0-9-]*)\s*([^"\n]*?)(?="|$|\n)/g;
        let match;
        
        while ((match = optionRegex.exec(usageContent)) !== null) {
            const [, flag, description] = match;
            
            args.push({
                flag: flag.trim(),
                description: description.trim(),
                type: 'boolean',
                source: 'usage'
            });
        }
        
        // Look for file parameter descriptions
        const filePatterns = [
            /<file\.mkv>/,
            /<.*\.mkv>/,
            /\[file\]/i,
            /\[input\]/i,
            /<input>/i
        ];
        
        for (const pattern of filePatterns) {
            if (pattern.test(usageContent)) {
                args.push({
                    flag: 'input',
                    description: 'Input MKV file to process',
                    type: 'file',
                    required: true,
                    accept: '.mkv',
                    source: 'usage'
                });
                break;
            }
        }
        
        return args;
    }

    // Parse case statements for argument handling
    parseCaseStatements() {
        const args = [];
        
        // Find case statements
        const caseRegex = /case\s+[^{]*?\s+in([\s\S]*?)esac/g;
        let caseMatch;
        
        while ((caseMatch = caseRegex.exec(this.content)) !== null) {
            const caseContent = caseMatch[1];
            
            // Extract case patterns
            const patternRegex = /(-[a-zA-Z]|\|--[a-zA-Z][a-zA-Z0-9-]*)\)/g;
            let patternMatch;
            
            while ((patternMatch = patternRegex.exec(caseContent)) !== null) {
                const flags = patternMatch[0].replace(')', '').split('|');
                
                flags.forEach(flag => {
                    flag = flag.trim();
                    if (flag && !args.some(arg => arg.flag === flag)) {
                        args.push({
                            flag,
                            description: this.extractCaseDescription(caseContent, flag),
                            type: 'boolean',
                            source: 'case'
                        });
                    }
                });
            }
        }
        
        return args;
    }

    // Extract description from case statement
    extractCaseDescription(caseContent, flag) {
        const lines = caseContent.split('\n');
        let foundFlag = false;
        
        for (const line of lines) {
            if (line.includes(flag)) {
                foundFlag = true;
                continue;
            }
            
            if (foundFlag) {
                // Look for comments or variable assignments that might describe the option
                const commentMatch = line.match(/#\s*(.+)/);
                if (commentMatch) {
                    return commentMatch[1].trim();
                }
                
                // Look for mode assignments
                const modeMatch = line.match(/OPERATION_MODE=["']([^"']+)["']/);
                if (modeMatch) {
                    return `Set operation mode to ${modeMatch[1]}`;
                }
                
                // Stop at the next case or break
                if (line.match(/;;|break/)) {
                    break;
                }
            }
        }
        
        return '';
    }

    // Parse arguments from comments
    parseCommentedArguments() {
        const args = [];
        
        for (let i = 0; i < this.lines.length; i++) {
            const line = this.lines[i];
            
            // Look for commented argument descriptions
            const commentMatch = line.match(/#\s*(-[a-zA-Z]|--[a-zA-Z][a-zA-Z0-9-]*)\s*:\s*(.+)/);
            if (commentMatch) {
                const [, flag, description] = commentMatch;
                
                args.push({
                    flag: flag.trim(),
                    description: description.trim(),
                    type: 'boolean',
                    source: 'comment'
                });
            }
        }
        
        return args;
    }

    // Detect file and directory arguments from script logic
    detectFileArguments() {
        const args = [];
        
        // Look for file validation patterns
        const fileValidationPatterns = [
            /if\s*\[\s*!\s*-f\s*["']?\$\{?([^}"\s]+)/g,  // if [ ! -f "$VAR" ]
            /\[\s*!\s*-f\s*["']?([^"'\s\]]+)/g,          // [ ! -f "file" ]
            /\*\.mkv/g,                                    // *.mkv pattern
            /\.mkv.*not.*found/i                          // error messages
        ];
        
        for (const pattern of fileValidationPatterns) {
            if (pattern.test(this.content)) {
                // Check if we already have a file input
                if (!args.some(arg => arg.type === 'file')) {
                    args.push({
                        flag: 'input',
                        description: 'Input MKV file to process',
                        type: 'file',
                        required: true,
                        accept: '.mkv',
                        source: 'detection'
                    });
                }
                break;
            }
        }
        
        // Look for directory operations
        const dirPatterns = [
            /dirname/,
            /mkdir\s+-p/,
            /\$\(dirname/
        ];
        
        for (const pattern of dirPatterns) {
            if (pattern.test(this.content)) {
                // This script works with directories but doesn't seem to take them as input
                break;
            }
        }
        
        return args;
    }

    // Merge duplicate arguments and combine information
    mergeDuplicates(args) {
        const merged = [];
        const flagMap = new Map();
        
        for (const arg of args) {
            const existing = flagMap.get(arg.flag);
            
            if (existing) {
                // Merge information, preferring more detailed sources
                existing.description = existing.description || arg.description;
                if (arg.source === 'usage' && existing.source !== 'usage') {
                    existing.description = arg.description || existing.description;
                }
                existing.type = arg.type || existing.type;
                existing.required = arg.required || existing.required;
                existing.accept = arg.accept || existing.accept;
            } else {
                flagMap.set(arg.flag, { ...arg });
                merged.push(arg);
            }
        }
        
        // Sort arguments: required first, then by flag
        return merged.sort((a, b) => {
            if (a.required && !b.required) return -1;
            if (!a.required && b.required) return 1;
            return a.flag.localeCompare(b.flag);
        });
    }

    // Extract additional metadata about the script
    getScriptMetadata() {
        const metadata = {
            description: '',
            version: '',
            author: '',
            requirements: []
        };
        
        // Look for header comments
        const headerLines = this.lines.slice(0, 20);
        for (const line of headerLines) {
            const comment = line.match(/#\s*(.+)/);
            if (comment) {
                const content = comment[1].trim();
                
                if (content.toLowerCase().includes('version')) {
                    metadata.version = content;
                } else if (content.toLowerCase().includes('author')) {
                    metadata.author = content;
                } else if (!metadata.description && content.length > 10) {
                    metadata.description = content;
                }
            }
        }
        
        // Detect requirements
        if (this.content.includes('docker')) {
            metadata.requirements.push('Docker');
        }
        if (this.content.includes('docker compose') || this.content.includes('docker-compose')) {
            metadata.requirements.push('Docker Compose');
        }
        if (this.content.includes('bash') || this.content.startsWith('#!/bin/bash')) {
            metadata.requirements.push('Bash');
        }
        
        return metadata;
    }

    // Detect operation modes
    getOperationModes() {
        const modes = [];
        
        // Look for MODE definitions
        const modeRegex = /MODE_([A-Z_]+)=["']([^"']+)["']/g;
        let match;
        
        while ((match = modeRegex.exec(this.content)) !== null) {
            const [, modeName, modeValue] = match;
            modes.push({
                name: modeName.toLowerCase(),
                value: modeValue,
                description: `${modeName.replace(/_/g, ' ').toLowerCase()} mode`
            });
        }
        
        return modes;
    }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScriptParser;
} else if (typeof window !== 'undefined') {
    window.ScriptParser = ScriptParser;
} 