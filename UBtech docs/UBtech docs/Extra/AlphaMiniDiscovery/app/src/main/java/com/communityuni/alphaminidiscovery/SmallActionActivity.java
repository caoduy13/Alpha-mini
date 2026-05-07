package com.communityuni.alphaminidiscovery;

import androidx.appcompat.app.AppCompatActivity;

import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ListView;

import com.communityuni.adapter.SmallActionAdapter;
import com.ubtrobot.small.action.SmallAction;
import com.ubtrobot.small.action.SmallActionApi;

public class SmallActionActivity extends AppCompatActivity {

    ListView lvSmallAction;
    SmallActionAdapter smallActionAdapter;
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_small_action);
        addControls();
        addEvents();
    }

    private void addEvents() {
        lvSmallAction.setOnItemClickListener(new AdapterView.OnItemClickListener() {
            @Override
            public void onItemClick(AdapterView<?> adapterView, View view, int i, long l) {
                SmallAction smallAction=smallActionAdapter.getItem(i);
                play(smallAction);
            }
        });
    }

    private void play(SmallAction smallAction) {
        SmallActionApi.get().play(smallAction);
    }

    private void addControls() {
        lvSmallAction=findViewById(R.id.lvSmallAction);
        smallActionAdapter=new SmallActionAdapter(this,R.layout.item_smallaction);
        lvSmallAction.setAdapter(smallActionAdapter);
        smallActionAdapter.addAll(SmallActionApi.get().listSmallActions());
    }
}
