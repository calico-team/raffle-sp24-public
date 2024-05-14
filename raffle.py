"""
Do the raffle!

Use -e to also display winner emails (not available in public version)

TODO add docs for how this mess actually works and maybe even refactor
"""

import random
import re
import sys
from collections import defaultdict

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Name of the column in raffle.csv whose values we will match with tickets.csv
# It doesn't need to be emails-- can be any string pretty much (ensure values match with values of below col)
RANKING_IDENTIFIER_COL = 'display_name'
# Values in this col (zero indexed) in tickets.csv should match up with the values in the column above in raffle.csv
TICKET_IDENTIFIER_COL_IDX = 0
# The column index in tickets.csv that gives the number of tickets for that row
TICKET_COUNT_COL_IDX = 1
# When we make the preference grid, google sheets starts each option with the question name
PRIZE_COL_STARTS_WITH = 'Raffle Prizes Ranking'
TICKET_CSV = 'data/processed/tickets.csv'
INVENTORY_CSV = 'data/raw/prizes.csv'
PREFERENCES_CSV = 'data/processed/preferences.csv'
SEED_TXT = 'data/raw/seed.txt'

def main():
    # you did this
    with open(SEED_TXT, 'r', encoding='utf8') as seed_file:
        seed = seed_file.read()
    random.seed(seed)

    # get all the stuffs
    identifier_to_team = load_identifier_to_team()
    team_to_tickets = load_team_to_tickets()
    dist, total = get_ticket_dist(identifier_to_team, team_to_tickets)
    inventory = get_inventory()
    prefs = get_preferences()
    """
    print("For Debugging:")
    print("len(dist): " + str(len(dist)))
    print(total)
    """
    # main logic
    while len(dist) > 0 and total > 0 and any(inventory.values()):# while there are contestants and prizes remaining
        person, total = draw_ticket(dist, total)
        
        assert person in prefs # if failed, this means draw_ticket selected someone that didnt fill out pref form
        
        person_prefs = prefs[person]
        # assuming we have preferences from 1 to max
        for i in range(1, len(inventory)+1):
            assert i in person_prefs # if failed, this means they didnt fill out all preferences
            
            selected_prize = person_prefs[i]
            if remove_inventory(inventory, selected_prize):
                print(f'{person} drew {selected_prize}. {inventory[selected_prize]} remain...')
                break
            else:
                pass # this means they didnt get the current prize, so we try the next prize
            
        


# returns the key (identifier) of the person drawn
def draw_ticket(dist, total):
    key = random.choices(list(dist.keys()), weights=list(dist.values()), k=1)[0]
    new_total = 0
    
    assert key is not None # if failed, then we inserted a ghost into the table somehow earlier in the process?
    
    new_total = total - dist[key]
    del dist[key]  # remove the person
    return key, new_total


def get_inventory():
    df = pd.read_csv(INVENTORY_CSV)
    df = df.sort_values(by=['name'])
    inventory = dict()

    for index, row in df.iterrows():
        inventory[row[0]] = row[1]

    return inventory


# returns false if failed
def remove_inventory(inventory, prize_name):
    if prize_name not in inventory or inventory[prize_name] == 0:
        return False
    inventory[prize_name] -= 1
    return True

REGISTRATION_TEAM_NAME_COL_IDX = 1
# Returns a mapping of identifiers -> prize preferences (which are rank -> prize name)
def get_preferences():
    df = pd.read_csv(PREFERENCES_CSV)
    df = df.sort_values(by=['display_name', 'team_name'])
    df = df[['display_name'] + [col for col in df.columns if col != 'display_name']]
    col = df.pop('team_name')
    df.insert(1, col.name, col)
    #df.drop('email', axis = 1, inplace=True)
    #print(df)
    
    
    # prize_id to prize name
    prizes = dict()
    
    col = ''
    i = prize_id = 0
    start_col = end_col = name_col = None
    for col in df.columns:
        if col == RANKING_IDENTIFIER_COL:
            name_col = i
        if col.startswith(PRIZE_COL_STARTS_WITH):
            if start_col is None:
                start_col = i
            prize = col[col.index('[') + 1:col.index(']')] # get prize name
            prizes[prize_id] = prize
            prize_id += 1
            end_col = i + 1
        i += 1
    people = dict()

    for index, row in df.iterrows():
        prize_id = 0
        ranks = dict()
        i = 0
        curr_name = ''
        curr_dict = dict()
        for value in row:
            # value is a ranking of that column's prize
            if i == name_col:
                ranks[value] = dict()
                curr_name = value
            if start_col <= i < end_col:
                # one of the prize columns
                curr_dict[value] = prizes[prize_id]
                prize_id += 1
            i += 1
        # assign people to their ranking preferences
        identifier = curr_name + ' (' + str(row[REGISTRATION_TEAM_NAME_COL_IDX]) + ')'
        
        if len(sys.argv) > 1 and '-e' in sys.argv[1:]:
            identifier = identifier + f' ({row["email"]})'
        
        people[identifier] = curr_dict
    return people



TEAM_MEMBER_COL_IDX = 0
def load_identifier_to_team():
    """
    df = pd.read_csv('data/processed/preferences.csv')
    df = df.sort_values(by=['display_name', 'team_name'])
    """
    df = pd.read_csv(PREFERENCES_CSV)
    df = df.sort_values(by=['display_name', 'team_name'])
    df = df[['display_name'] + [col for col in df.columns if col != 'display_name']]
    col = df.pop('team_name')
    df.insert(1, col.name, col)
    d = dict() # identifier -> team
    for index, row in df.iterrows():
        team = str(row[REGISTRATION_TEAM_NAME_COL_IDX])
        identifier = row[TEAM_MEMBER_COL_IDX] + ' (' + team + ')'
        
        if len(sys.argv) > 1 and '-e' in sys.argv[1:]:
            identifier = identifier + f' ({row["email"]})'
        
        d[identifier] = team
    return d


SCORE_COL_IDX = 1
TEAM_NAME_COL_IDX = 0
def load_team_to_tickets() -> dict():
    df = pd.read_csv('data/processed/tickets.csv')
    df = df.sort_values(by=['team_name'])
    d = dict() # team -> tickets
    for index, row in df.iterrows():
        tickets = int(row[SCORE_COL_IDX])
        d[row[TEAM_NAME_COL_IDX]] = tickets
    return d


def get_ticket_dist(identifier_to_team, team_to_tickets):
    d = dict() # identifier -> tickets
    total = 0
    
    for identifier in identifier_to_team:
        team = identifier_to_team[identifier]
        #print(identifier_to_team) 
        assert team in team_to_tickets # if failed, then this team is found in registrations but not on scoreboard?
        
        d[identifier] = team_to_tickets[team]
        total += d[identifier]
        
    return d, total


if __name__ == '__main__':
    print('Raffling...')
    main()
    print('Done!')
