import operator
import os
from datetime import timedelta, datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from wordcloud import WordCloud

DATA_FILE = os.environ.get('DATA_FILE', 'kolab_messages.csv')
DATA_REV = datetime.fromtimestamp(os.stat(DATA_FILE).st_mtime)

st.set_page_config(page_title='KoLab Discord stats', page_icon=':chart_with_upwards_trend:', layout="wide")
st.markdown(r"""<style>
                .stAppDeployButton { visibility: hidden; }
                </style>
                """, unsafe_allow_html=True)
st.title("KoLab Discord stats")


def get_messages() -> pd.DataFrame:
    return _get_messages(rev=DATA_REV)


@st.cache_data(ttl=3600, show_spinner=True)
def _get_messages(rev) -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    df['author_created'] = pd.to_datetime(df['author_created'], format='ISO8601')
    df = df[~df['content'].isna()]
    df = df.sort_values(by='timestamp').reset_index(drop=True)

    # Distinguish between new users and existing users:
    authors = (df[['timestamp', 'author_name', 'author_created']]
               .groupby(['author_name', 'author_created'])
               .aggregate({'timestamp': 'min'}).reset_index())
    authors['new_user'] = ((pd.to_datetime(authors['timestamp']) - pd.to_datetime(authors['author_created'])) <=
                           timedelta(days=2))

    # Merge `new_user` column into main dataframe:
    return df.merge(authors[['author_name', 'new_user']], on='author_name', how='left')


@st.cache_data(ttl=3600, show_spinner=True)
def get_mau(rev) -> pd.DataFrame:
    df = _get_messages(rev)

    # Aggregate by user and date:
    df.loc[:, 'date'] = df['timestamp'].dt.date
    mau = df[['date', 'author_name']].drop_duplicates()
    mau['date'] = pd.to_datetime(mau['date'])

    # Create a contiguous date range
    date_range = pd.date_range(start=mau['date'].min(), end=mau['date'].max(), freq='D')

    # For each date, count unique users in the prior 30 days
    mau_list = []
    for current_date in date_range:
        # Get dates from 30 days ago up to (and including) current date
        window_start = current_date - pd.Timedelta(days=30)

        # Find all unique users active in this window
        active_users = mau[(mau['date'] > window_start) & (mau['date'] <= current_date)]['author_name'].nunique()

        mau_list.append({'date': current_date, 'MAU': active_users})

    return pd.DataFrame(mau_list)


@st.cache_data(ttl=3600, show_spinner=True)
def get_dau(rev) -> pd.DataFrame:
    # Aggregate by user and date:
    dau = (_get_messages(rev)
           .assign(date=lambda x: x['timestamp'].dt.date)
           [['date', 'author_name']]
           .drop_duplicates()
           .groupby(['date'])
           .aggregate({'author_name': 'count'})
           .reset_index()
           .rename(columns={'author_name': 'DAU'}))

    return (dau
            .set_index('date')
            .reindex(pd.date_range(start=dau['date'].min(), end=dau['date'].max(), freq='D'))
            .reset_index()
            .rename(columns={'index': 'date'})
            .fillna(0))


@st.cache_data(ttl=3600, show_spinner=True)
def get_rentention_rates(retention_days: int, usernames: set | None = None, rev = None) -> pd.DataFrame:
    df = _get_messages(rev)
    # exclude users that joined less than 2 * retention_days days ago:
    selected_users = set(df[df['timestamp'] < (df['timestamp'].max() - timedelta(days=2 * retention_days))]
                         ['author_name'].unique())

    retention = []
    for username in (selected_users if usernames is None else usernames):
        cr = df[df['author_name'] == username]
        cr.loc[:, 'timestamp'] = pd.to_datetime(cr['timestamp'])
        joined = cr['timestamp'].iloc[0]
        converted = 0 if cr[(cr['timestamp'] > joined + timedelta(days=retention_days)) & (
                    cr['timestamp'] <= joined + timedelta(days=2 * retention_days))].empty else 1
        retention.append({'author_name': username, 'joined': joined, 'retained': converted})

    retention = pd.DataFrame(retention).sort_values('joined').reset_index(drop=True)
    return retention


@st.cache_data(ttl=3600, show_spinner=True)
def get_message_count_by_channel(days: int | None = 30, rev = None) -> pd.DataFrame:
    msgs = _get_messages(rev)
    if days is not None:
        df = msgs[msgs['timestamp'] > (msgs['timestamp'].max() - timedelta(days=days))]
    return (df.groupby(['channel_name', 'author_name', 'author_avatar'])
            .size()
            .reset_index(name='messages')
            .groupby('channel_name')
            .apply(lambda x: pd.Series({'count': x['messages'].sum(),
                                        'author_avatar': x.loc[x['messages'].idxmax(), 'author_avatar'],
                                        'author_name': x.loc[x['messages'].idxmax(), 'author_name'],
                                        }))
            .reset_index()
            .merge(msgs[['channel_name']].drop_duplicates(), on='channel_name', how='outer')
            .assign(count=lambda _df: _df['count'].fillna(0).astype(int)))


@st.cache_data(ttl=3600, show_spinner=True)
def draw_wordcloud(days: int, rev, theme: str) -> None:
    freqs = get_message_count_by_channel(days=days, rev=DATA_REV).sort_values(by='count', ascending=False)
    frequencies = {s.iloc[0]: s.iloc[1] for _, s in freqs.iterrows() if s.iloc[1] > 0}
    wc = (WordCloud(background_color='white' if st.context.theme.type == 'light' else '#0e1016',
                    width=2048, height=1024)
          .generate_from_frequencies(frequencies))
    st.image(wc.to_array(), width='stretch')

    df = get_messages().assign(date=lambda x: x['timestamp'].dt.date)
    if days is not None:
        df = df[df['date'] > (df['date'].max() - timedelta(days=days))]
    df = (df
          .assign(date=lambda x: x['timestamp'].dt.date)
          .groupby(['date', 'channel_name'])
          .size()
          .reset_index(name='messages'))
    total_by_date = df.groupby('date')['messages'].sum().reset_index()
    total_by_date['ma_30'] = total_by_date['messages'].rolling(window=30, min_periods=1).mean()
    st.plotly_chart(px.bar(df, x='date', y='messages', color='channel_name', title='',
                           labels={'channel_name': 'Channel'}).update_layout(xaxis_title=None)
                    .add_scatter(x=total_by_date['date'], y=total_by_date['ma_30'], mode='lines', name='30-day avg',
                                 line=dict(color='black', dash='dash')),
                    width='stretch')

f"""
Some engagement statistics derived from the message history of the publicly accessible channels.

Data as of: {DATA_REV.strftime('%Y-%m-%d %H:%M:%S')}

[Open Discord](https://discord.gg/3dWQGzWTsy)
"""

st.header('User activity', divider=True)
cols = st.columns(2)
with cols[0]:
    mau = get_mau(DATA_REV)
    st.metric(label='Monthly active users', value=mau.tail(1)['MAU'].values[0], border=True,
              delta=operator.sub(*list(mau.tail(2)['MAU'])[::-1]), width='content',
              help='Users who have sent one or mores messages in the last 30 days')
    # Calculate 30-day trailing average
    mau['MAU_30d_avg'] = mau['MAU'].rolling(window=30, min_periods=1).mean()

    fig = px.line(mau, x='date', y=['MAU', 'MAU_30d_avg'],
                  title='Monthly Active Users (MAU)',
                  labels={'date': 'Date', 'value': 'Monthly Active Users'})

    fig.update_traces(patch={"line": {"dash": 'dash'}}, selector={"legendgroup": 'MAU_30d_avg'})
    fig.update_layout(hovermode='x unified')
    st.plotly_chart(fig, width='stretch')

    # Total server users chart:
    users = (get_messages()[['timestamp', 'author_name']]
             .groupby(['author_name'])
             .aggregate({'timestamp': 'min'})
             .sort_values(by='timestamp')
             .reset_index()
             .assign(count=lambda x: range(1, len(x) + 1)))
    st.plotly_chart(px.line(users, x='timestamp', y='count', title='Total server users',
                            labels={'count': 'Total users'})
                    .update_layout(xaxis_title=None),
                    width='stretch')

with cols[1]:
    dau = get_dau(DATA_REV)
    dau_30d = dau.tail(30)['DAU'].mean()
    st.metric(label='Daily active users', value=f'{dau_30d:.2f}', border=True,
              delta=f"{dau_30d - dau.iloc[-31:-1]['DAU'].mean():.2f}",
              width='content', help='The number of active users per day, averaged over the past 30 days')

    # Calculate 30-day trailing average
    dau['DAU_30d_avg'] = dau['DAU'].rolling(window=30, min_periods=1).mean()

    fig = (px.line(dau, x='date', y=['DAU', 'DAU_30d_avg'], title='Daily Active Users (DAU)',
                   labels={'date': 'Date', 'value': 'Daily Active Users'})
           .update_traces(patch={"line": {"dash": 'dash'}}, selector={"legendgroup": 'DAU_30d_avg'})
           .update_layout(hovermode='x unified'))
    st.plotly_chart(fig, width='stretch')

st.header('Channel activity', divider=True)
try:
    act_int = st.selectbox(label='Activity by channel over the past days', options=[7, 30, 365, 'All time'], index=1,
                           accept_new_options=True, key='activity_interval')
    act_int = None if act_int == 'All time' else int(act_int)
except ValueError:
    st.error(f'Invalid input: {st.session_state.activity_interval}. Select a valid number of days.')
    act_int = 7

cols = st.columns([2, 1])
with cols[0]:
    draw_wordcloud(act_int, rev=DATA_REV, theme=st.context.theme.type)
with cols[1]:
    freqs = get_message_count_by_channel(days=act_int, rev=DATA_REV).sort_values(by=['count', 'channel_name'],
                                                                                 ascending=[False, True])
    st.dataframe(freqs, hide_index=True, height=850,
                 column_config={
                     'channel_name': st.column_config.Column(label='Channel'),
                     'count': st.column_config.ProgressColumn(label='Total messages', format='%d',
                                                              max_value=int(freqs['count'].max())),
                     'author_avatar': st.column_config.ImageColumn(label='', width=10),
                     'author_name': st.column_config.Column(label='Most active member')})

st.header('Retention rates', divider=True)
"""
How many new joiners are retained and convert into active community members? Following Discord's own retention rate
definition, a user is considered retained when they show activity in the second week after joining the server.
"""

cols = st.columns([1, 3])
with cols[0]:
    joiners = (get_messages()[['author_name', 'new_user']]
               .drop_duplicates()
               .groupby(['new_user'])
               .size()
               .reset_index(name='count'))
    joiners.loc[:, 'kind'] = joiners['new_user'].map(lambda v: 'New to Discord' if v else 'Existing Discord user')
    fig = px.pie(joiners, values='count', names='kind')
    st.plotly_chart(fig, width='content')
    st.write("When new users join, are they existing Discord users or did they have to create a new Discord account?")

with cols[1]:
    st.markdown("""
        We can explore different retention periods. Retention is defined as having activity in the second retention
        period after joining.

        So if the selected retention period is 14 days, a user is retained if they have sent a message between day 8
        and 14 after joining.""")

    try:
        days = int(st.selectbox(label='Retention period (days)', options=[1, 7, 14, 30, 90], index=1,
                                key='retention_period', accept_new_options=True,
                                help='Select the number of days over which to calculate retention rates.'))
    except ValueError:
        st.error(f'Invalid input: {st.session_state.retention_period}. Select a valid number of days.')
        days = 7

    _cols = st.columns(3)
    with _cols[0]:
        rates = get_rentention_rates(retention_days=days)
        rate = rates['retained'].sum() / len(rates) * 100
        st.metric(label='Global, all-time new joiner retention rate', value=f'{rate:.2f}%', border=True)
        st.markdown(f"Across all users, how many people remain active on the server after {days} days?")

    with _cols[1]:
        new_users = get_messages().query('new_user == True')['author_name'].drop_duplicates()
        rates = get_rentention_rates(retention_days=days, usernames=set(new_users), rev=DATA_REV)
        rate = rates['retained'].sum() / len(rates) * 100
        st.metric(label='Retention of newly created accounts', value=f'{rate:.2f}%', border=True)
        st.markdown(
            "How about users that were not already on Discord and had to create an account specifically to join KoLab?")
        st.markdown(
            "We'd expect this number to be greater than the global figure as these users crossed a higher barrier.")

    with _cols[2]:
        existing_users = get_messages().query('new_user == False')['author_name'].drop_duplicates()
        rates = get_rentention_rates(retention_days=days, usernames=set(existing_users), rev=DATA_REV)
        rate = rates['retained'].sum() / len(rates) * 100
        st.metric(label='Retention of existing accounts', value=f'{rate:.2f}%', border=True)
        st.markdown("And what about existing Discord users that had a lower barrier to join KoLab?")
        st.markdown("We'd expect this number to be lower than the global figure.")

    st.info("""
        Users that never post any message after joining, are excluded from these calculations.
        Possibly due to our Discord's mandatory onboarding process, this is a non-negligible number.
        Anecdotally, in a recent 2 week period, 12 new users joined, of which 6 never even passed the verify channel.

        If these users a considered, our retention metrics would be significantly lower than the global figure.
        """, icon=":material/info:")

st.header('Source data', divider=True)
st.markdown(f'The raw data and code used for these reports is available [here](app/static/{os.path.basename(DATA_FILE)}).')

with st.expander('Source code'):
    with open(__file__, 'r') as f:
        st.code(f.read(), line_numbers=True)
