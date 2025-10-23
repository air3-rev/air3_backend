#!/usr/bin/env python3
"""
Script to check if provided journal titles exist in category_journals.json
and retrieve their ISSN numbers.
"""
import json
from typing import Dict, Set, List

def load_journals_data(file_path: str) -> Dict[str, Set[str]]:
    """
    Load category_journals.json and build a mapping from journal title to set of ISSNs.
    """
    with open(file_path, 'r') as f:
        data = json.load(f)

    title_to_issns = {}
    for category, journals in data.items():
        for journal in journals:
            title = journal['title']
            issns_str = journal['issn']
            issns = {issn.strip() for issn in issns_str.split(', ') if issn.strip()}
            if title in title_to_issns:
                title_to_issns[title].update(issns)
            else:
                title_to_issns[title] = issns
    return title_to_issns

def main():
    # Provided journal titles from the task
    target_journals = [
        "Academy of Management Journal",
        "Academy of Management Review",
        "Accounting, Organizations and Society",
        "Administrative Science Quarterly",
        "American Economic Review",
        "Contemporary Accounting Research",
        "Econometrica",
        "Entrepreneurship Theory and Practice",
        "Harvard Business Review",
        "Human Relations",
        "Human Resource Management",
        "Information Systems Research",
        "Journal of Accounting and Economics",
        "Journal of Accounting Research",
        "Journal of Applied Psychology",
        "Journal of Business Ethics",
        "Journal of Business Venturing",
        "Journal of Consumer Psychology",
        "Journal of Consumer Research",
        "Journal of Finance",
        "Journal of Financial and Quantitative Analysis",
        "Journal of Financial Economics",
        "Journal of International Business Studies",
        "Journal of Management",
        "Journal of Management Information Systems",
        "Journal of Management Studies",
        "Journal of Marketing",
        "Journal of Marketing Research",
        "Journal of Operations Management",
        "Journal of Political Economy",
        "Journal of the Academy of Marketing Science",
        "Management Science",
        "Manufacturing and Service Operations Management",
        "Marketing Science",
        "MIS Quarterly",
        "Operations Research",
        "Organization Science",
        "Organization Studies",
        "Organizational Behavior and Human Decision Processes",
        "Production and Operations Management",
        "Quarterly Journal of Economics",
        "Research Policy",
        "Review of Accounting Studies",
        "Review of Economic Studies",
        "Review of Finance",
        "Review of Financial Studies",
        "Sloan Management Review",
        "Strategic Entrepreneurship Journal",
        "Strategic Management Journal",
        "The Accounting Review"
    ]

    # Load the journals data
    file_path = '../data/category_journals.json'
    title_to_issns = load_journals_data(file_path)

    # Check each target journal
    unique_issns = set()
    missing_journals = []

    for title in target_journals:
        if title in title_to_issns:
            unique_issns.update(title_to_issns[title])
        else:
            missing_journals.append(title)

    # Output results
    print("Unique ISSN numbers for existing journals:")
    for issn in sorted(unique_issns):
        print(f"  {issn}")

    print(f"\nTotal unique ISSNs: {len(unique_issns)}")

    print("\nMissing journals:")
    for journal in missing_journals:
        print(f"  {journal}")

    print(f"\nTotal missing journals: {len(missing_journals)}")

if __name__ == "__main__":
    main()