#!/usr/bin/env python3

# Read the file
with open('/Users/chance/quarto-lab/theory/Topics/Shadow_tomography/multi-copy-shadow.qmd', 'r') as f:
    lines = f.readlines()

# Find the line with "can then be estimated" and replace from there
output_lines = []
i = 0
while i < len(lines):
    if i < len(lines) - 5 and 'can then be estimated by calculating the estimator' in lines[i]:
        # Found the target line, add it
        output_lines.append(lines[i])
        # Skip the next line with the formula and "To realize..."
        i += 1
        output_lines.append(lines[i])  # Add the formula line
        i += 1

        # Now add the new Step 4 section
        output_lines.append('\n')
        output_lines.append('**Step 4: Circuit implementation**\n')
        output_lines.append('\n')
        output_lines.append('To realize such a measurement, we refer to the construction in [@liu2024auxiliary] and note that:\n')

        # Skip the old "To realize..." lines until we hit the $$
        while i < len(lines) and not lines[i].strip().startswith('$$'):
            i += 1
        # Continue with the rest of the file
    elif i < len(lines) - 10 and 'This disentangled the qubit on the third and the forth' in lines[i]:
        # Fix grammar and add Step 5
        output_lines.append('$$\n')
        output_lines.append('\n')
        output_lines.append('This disentangles the qubits on the third and fourth copies. Thus, we can locally implement the gate sequence $\\mathrm{CNOT}_{13}\\mathrm{CNOT}_{24}\\mathrm{H}_3\\mathrm{H}_1\\mathrm{CNOT}_{12}\\mathrm{CNOT}_{34}$ and then measure the 3rd and 4th copies in the computational basis $\\ket{\\mathbf{s}_{3}\\mathbf{s}_4}$.\n')
        output_lines.append('\n')
        output_lines.append('**Step 5: Extract measurement outcomes**\n')
        output_lines.append('\n')
        output_lines.append('The computational basis measurement gives the difference of vectors $\\mathbf{a}$ and $\\mathbf{b}$ through:\n')
        output_lines.append('$$\n')
        output_lines.append('\\mathbf{s}_{3} = \\mathbf{a}_x + \\mathbf{b}_x,\\quad \\mathbf{s}_{4} = \\mathbf{a}_z + \\mathbf{b}_z\n')
        output_lines.append('$$\n')
        output_lines.append('\n')
        output_lines.append('This information indicates a partition of the 1st and 2nd copies of qubits $\\{1,\\cdots,2n\\} = E \\cup I$, where:\n')
        output_lines.append('- $E := \\{i \\in [2n]| a_i = b_i\\}$ (equal indices)\n')
        output_lines.append('- $I:= \\{i \\in [2n]| \\bar{a}_i = b_i\\} := \\{i_1<i_2<\\cdots<i_{|I|}\\}$ (inverted indices)\n')
        output_lines.append('\n')
        output_lines.append('We then implement:\n')
        output_lines.append('1. Computational basis measurement $\\ket{\\mathbf{s}^{E}}$ on qubits in set $E$\n')
        output_lines.append('2. GHZ state measurement $s^{I}$ on qubits in set $I$, formalized by the circuit:\n')
        output_lines.append('\n')

        # Skip old text until we find the equation
        while i < len(lines) and not ('$$\\begin{align}' in lines[i] or '$$' in lines[i] and '\\begin{align}' in lines[i+1] if i+1 < len(lines) else False):
            i += 1
        # Continue with the equation
    elif i < len(lines) - 3 and 'Here we use the fact that since' in lines[i]:
        # Add the closing of the proof block
        output_lines.append(lines[i])
        i += 1
        output_lines.append(lines[i])  # "we have..."
        i += 1
        output_lines.append(lines[i])  # formula line 1
        i += 1
        output_lines.append(lines[i])  # formula line 2
        i += 1
        output_lines.append('\n')
        output_lines.append(':::\n')
        output_lines.append('\n')
    else:
        output_lines.append(lines[i])
        i += 1

# Write back
with open('/Users/chance/quarto-lab/theory/Topics/Shadow_tomography/multi-copy-shadow.qmd', 'w') as f:
    f.writelines(output_lines)

print("Done!")
