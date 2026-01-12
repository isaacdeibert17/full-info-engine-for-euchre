import streamlit as st
import copy

# --- CONSTANTS & CONFIG ---
LB_SUITS = {'Hearts': 'Diamonds', 'Diamonds': 'Hearts', 'Clubs': 'Spades', 'Spades': 'Clubs'}
SUIT_MAP = {'H': 'Hearts', 'D': 'Diamonds', 'C': 'Clubs', 'S': 'Spades'}

class Card:
    def __init__(self, rank, suit):
        self.rank, self.suit = rank, suit
    def __str__(self): return f"{self.rank}{self.suit[0]}"
    def get_effective_suit(self, trump):
        if self.rank == 'J' and self.suit == LB_SUITS[trump]: return trump
        return self.suit
    def strength(self, trump, lead=None):
        if self.rank == 'J' and self.suit == trump: return 100
        if self.rank == 'J' and self.suit == LB_SUITS[trump]: return 99
        if self.suit == trump: return 90 + ['9', '10', 'Q', 'K', 'A'].index(self.rank)
        if lead and self.get_effective_suit(trump) == lead: return 70 + ['9', '10', 'J', 'Q', 'K', 'A'].index(self.rank)
        return 50 + ['9', '10', 'J', 'Q', 'K', 'A'].index(self.rank)

def parse_card(s):
    s = s.upper().strip().replace(" ", "")
    if not s: return None
    try: return Card(s[:-1], SUIT_MAP[s[-1]])
    except: return None

# --- ENGINE ---

# FIX: We pass 'hand_sig' (a string) which Streamlit CAN read/hash. 
# This forces it to re-run the math whenever the cards text changes.
@st.cache_data
def get_best_move_cached(hand_sig, _hands, trump, leader, current_trick, alpha, beta, loner_pos=None):
    return get_best_move(_hands, trump, leader, current_trick, alpha, beta, loner_pos)

def get_best_move(hands, trump, leader, current_trick, alpha, beta, loner_pos=None):
    if not any(hands[i] for i in hands): return 0, [], 1
    
    active = [0, 1, 2, 3]
    if loner_pos is not None:
        partner = (loner_pos + 2) % 4
        if partner in active: active.remove(partner)
    
    p = (leader + len(current_trick)) % 4
    while p not in active:
        current_trick.append(None)
        p = (leader + len(current_trick)) % 4

    ls = next((c.get_effective_suit(trump) for c in current_trick if c), None)
    legal = [c for c in hands[p] if c.get_effective_suit(trump) == ls] or hands[p]
    
    is_max = (p % 2 == 0)
    val = -100 if is_max else 100
    best_log, total_paths = [], 0

    for card in sorted(legal, key=lambda x: x.strength(trump, ls), reverse=True):
        new_hands = {i: [c for c in hands[i] if c != card] for i in hands}
        if len(current_trick) + 1 < 4:
            res, log, paths = get_best_move(new_hands, trump, leader, current_trick + [card], alpha, beta, loner_pos)
        else:
            full_t = current_trick + [card]
            winner = (leader + max(range(4), key=lambda i: full_t[i].strength(trump, next((c.get_effective_suit(trump) for c in full_t if c), None)) if full_t[i] else -1)) % 4
            res, log, paths = get_best_move(new_hands, trump, winner, [], alpha, beta, loner_pos)
            res += (1 if winner % 2 == 0 else 0)
            
            # Bolding Logic for P0
            trick_str_list = []
            for i, c in enumerate(full_t):
                if c is None: 
                    trick_str_list.append("SKIP")
                else:
                    player_id = (leader + i) % 4
                    c_txt = str(c)
                    trick_str_list.append(f"**{c_txt}**" if player_id == 0 else c_txt)
            
            log = [f"P{winner} wins trick: {', '.join(trick_str_list)}"] + log

        if is_max:
            if res > val: val, best_log, total_paths = res, log, paths
            elif res == val: total_paths += paths
            alpha = max(alpha, val)
        else:
            if res < val: val, best_log, total_paths = res, log, paths
            elif res == val: total_paths += paths
            beta = min(beta, val)
        if beta <= alpha: break
    
    return max(0, min(5, val)) if val not in [-100, 100] else 0, best_log, total_paths

# --- STREAMLIT UI ---
def main():
    st.set_page_config(page_title="Bower Ranger Engine", layout="wide")
    st.title("🃏 Bower Ranger: Full Info Engine")

    if st.sidebar.button("🧹 Force Reset"):
        st.cache_data.clear()
        st.sidebar.success("Memory cleared!")

    # 1. PLAYER HANDS - Defaults set to unique cards
    st.subheader("1. Enter Player Hands")
    col1, col2 = st.columns(2)
    with col1:
        p0_in = st.text_input("P0 (You)", "JD,9D,AH,QH,10S")
        p2_in = st.text_input("P2 (Partner)", "AD,KD,JH,10H,9H")
    with col2:
        p1_in = st.text_input("P1 (Left)", "AS,KS,QS,JS,9S")
        p3_in = st.text_input("P3 (Right)", "AC,KC,QC,JC,10C")

    # 2. CONTEXT
    st.subheader("2. Face-Up & Dealer")
    col3, col4 = st.columns(2)
    with col3:
        up_c_in = st.text_input("Face-Up Card", "9C")
    with col4:
        dealer_pos = st.selectbox("Dealer Position", [0, 1, 2, 3], format_func=lambda x: f"Player {x}")

    # Process Data
    hands = {0: [parse_card(c) for c in p0_in.split(',')], 1: [parse_card(c) for c in p1_in.split(',')],
             2: [parse_card(c) for c in p2_in.split(',')], 3: [parse_card(c) for c in p3_in.split(',')]}
    up_c = parse_card(up_c_in)

    # 3. ANALYSIS
    st.divider()
    st.subheader("3. Interactive Analysis")
    a1, a2, a3 = st.columns(3)
    with a1:
        call_suit = st.selectbox("Suit to Call", ['Hearts', 'Diamonds', 'Clubs', 'Spades'])
    with a2:
        caller_idx = st.selectbox("Caller", [0, 1, 2, 3])
    with a3:
        go_alone = st.checkbox("Loner?")

    if st.button("🔍 Run Full Simulation", use_container_width=True):
        work_hands = copy.deepcopy(hands)
        
        # Helper to create a unique ID for the hands for caching
        hand_signature = p0_in + p1_in + p2_in + p3_in + str(dealer_pos) + str(up_c_in)

        # --- DISCARD ANALYSIS ---
        if up_c and call_suit == up_c.suit:
            st.write(f"### 📋 Discard Analysis for P{dealer_pos}")
            discard_options = work_hands[dealer_pos] + [up_c]
            best_d_score = -1 if dealer_pos % 2 == 0 else 6
            best_d_card = None
            table_results = []

            for disc in discard_options:
                temp_h = copy.deepcopy(work_hands)
                temp_h[dealer_pos] = [c for c in discard_options if str(c) != str(disc)]
                
                # Pass signature to force refresh
                sc, _, _ = get_best_move_cached(hand_signature + str(disc), temp_h, call_suit, (dealer_pos+1)%4, [], -100, 100, caller_idx if go_alone else None)
                table_results.append({"Discarding": str(disc), "Team 0/2 Tricks": sc})
                
                if (dealer_pos % 2 == 0 and sc > best_d_score) or (dealer_pos % 2 != 0 and sc < best_d_score):
                    best_d_score, best_d_card = sc, disc
            
            st.table(table_results)
            work_hands[dealer_pos] = [c for c in discard_options if str(c) != str(best_d_card)]
            st.success(f"**Optimal Play:** Dealer P{dealer_pos} discards **{best_d_card}**.")

        # --- FINAL CALCULATION ---
        # We pass 'hand_signature' to the cached function. 
        # If you change the text inputs, this signature changes, forcing a new calculation.
        score, log, paths = get_best_move_cached(hand_signature, work_hands, call_suit, (dealer_pos+1)%4, [], -100, 100, caller_idx if go_alone else None)
        
        m1, m2 = st.columns(2)
        m1.metric("Predicted Tricks (Team 0/2)", score)
        m2.metric("Optimal Strategy Paths", paths)
        
        with st.expander("See Detailed Strategy Log (Your cards in **BOLD**)"):
            for line in log:
                st.markdown(line)

if __name__ == "__main__":
    main()